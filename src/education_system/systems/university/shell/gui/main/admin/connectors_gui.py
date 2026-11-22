"""Standalone Tk window for the institutional connectors, the university
event queue and record retention (admin only) — mirrors sso_providers_gui.

Launched as a subprocess by the main GUI (``_NEW_FEATURE_MODULES``); the
signed-in user arrives via ``require_launcher_auth``. Three tabs:

* Connectors - switch each on/off, choose the transport (a daily file to
  upload, or HTTPS with a token from the environment / var/secrets), see
  what it has sent (``application/connectors``).
* Event queue - waiting and dead-lettered events with their errors, the
  student lifecycle actions not yet done, requeue, run a pass now
  (``application/outbox_dispatcher``).
* Record retention - what is past its period, and disposal on/off per
  record type (``domains/governance/infrastructure/data_lifecycle_store``).

No DB access at import time.
"""
from __future__ import annotations

import logging
import pathlib
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

from education_system.systems.university.application import (  # noqa: E402
    connectors,
    outbox_dispatcher,
)
from education_system.systems.university.domains.governance.infrastructure import (  # noqa: E402
    data_lifecycle_store,
)
from education_system.systems.university.infrastructure.auth import sso_admin  # noqa: E402
from education_system.systems.university.infrastructure.connector_adapters import (  # noqa: E402
    OUTBOUND_DIR,
)
from education_system.systems.university.infrastructure.i18n import get_text as _t  # noqa: E402

logger = logging.getLogger(__name__)

TITLE = "Connectors & Event Queue"
RETENTION_TYPES = ("applicant", "student_record")


def _tree(parent, cols, widths, stretch):
    tree = ttk.Treeview(parent, columns=cols, show="headings")
    for col, width in zip(cols, widths):
        tree.heading(col, text=col.replace("_", " ").title())
        tree.column(col, width=width, stretch=col == stretch)
    return tree


def _fill(tree, rows):
    for item in tree.get_children():
        tree.delete(item)
    for values in rows:
        tree.insert("", "end", values=values)


class ConnectorsApp(tk.Frame):
    def __init__(self, parent, user=None):
        super().__init__(parent)
        self._user = user or {}
        self._actor = str(self._user.get("username") or self._user.get("id") or "unknown")
        self._build()
        self.refresh()

    # ── layout ──────────────────────────────────────────────────────────

    def _build(self):
        header = tk.Frame(self, bg="#2c3e50")
        header.pack(fill="x")
        tk.Label(header, text=_t("gui.admin.connectors.title", default=TITLE),
                 font=("Helvetica", 14, "bold"), bg="#2c3e50", fg="white").pack(
            side="left", padx=16, pady=8)
        tk.Label(header, text=f"Signed in: {self._actor} ({self._user.get('role') or '-'})",
                 bg="#2c3e50", fg="#bdc3c7").pack(side="right", padx=16)
        book = ttk.Notebook(self)
        book.pack(fill="both", expand=True, padx=8, pady=8)
        book.add(self._connectors_tab(book), text="Connectors")
        book.add(self._queue_tab(book), text="Event queue")
        book.add(self._retention_tab(book), text="Record retention")

    def _bar(self, parent, buttons):
        bar = tk.Frame(parent)
        bar.pack(fill="x", pady=(0, 6))
        for label, cmd in buttons:
            ttk.Button(bar, text=label, command=cmd).pack(side="left", padx=4)

    def _connectors_tab(self, book):
        tab = tk.Frame(book)
        self._bar(tab, (("Refresh", self.refresh), ("Configure…", self.configure),
                        ("Switch on", lambda: self.set_enabled(True)),
                        ("Switch off", lambda: self.set_enabled(False)),
                        ("What it sent", self.show_receipts)))
        tk.Label(tab, anchor="w", fg="#555555",
                 text=f"File transport writes {OUTBOUND_DIR}/<connector>/<date>.jsonl "
                      "for staff to upload; HTTP posts JSON to an https:// endpoint.").pack(
            fill="x")
        self._connectors = _tree(
            tab, ("connector", "on", "transport", "status", "sent", "last_checked", "last_error"),
            (150, 50, 80, 90, 60, 140, 380), "last_error")
        self._connectors.pack(fill="both", expand=True)
        return tab

    def _queue_tab(self, book):
        tab = tk.Frame(book)
        self._bar(tab, (("Refresh", self.refresh), ("Requeue selected", self.requeue),
                        ("Run a pass now", self.run_now)))
        self._summary = tk.Label(tab, anchor="w")
        self._summary.pack(fill="x")
        panes = ttk.PanedWindow(tab, orient="vertical")
        panes.pack(fill="both", expand=True)
        self._events = _tree(
            panes, ("event_id", "state", "event", "about", "tries", "next_try", "last_error"),
            (290, 80, 220, 110, 50, 170, 360), "last_error")
        panes.add(self._events, weight=3)
        self._actions = _tree(
            panes, ("action_id", "student", "area", "action", "status", "tries", "last_error"),
            (70, 100, 140, 140, 80, 50, 400), "last_error")
        panes.add(self._actions, weight=2)
        return tab

    def _retention_tab(self, book):
        tab = tk.Frame(book)
        self._bar(tab, (("Refresh", self.refresh),
                        ("Turn disposal on", lambda: self.set_retention(True)),
                        ("Turn disposal off", lambda: self.set_retention(False))))
        tk.Label(tab, anchor="w", justify="left", fg="#555555",
                 text="Applicants who never enrolled are redacted two years after their last "
                      "contact; closed student records lose personal contact details after "
                      "seven years.\nLegal holds block disposal. Finance, health and "
                      "safeguarding records have their own retention jobs.").pack(fill="x")
        self._retention = _tree(tab, ("record_type", "disposal", "due_now", "period", "action"),
                                (160, 90, 90, 120, 120), "action")
        self._retention.pack(fill="both", expand=True)
        return tab

    # ── data ────────────────────────────────────────────────────────────

    def refresh(self):
        try:
            _fill(self._connectors, [
                (c["connector_name"], "yes" if c["enabled"] else "no",
                 c["config"].get("transport", "file"), c["status"], c["receipts"],
                 str(c["last_checked_at"] or "")[:19], c["last_error"] or "")
                for c in connectors.overview()])
            s = outbox_dispatcher.summary()
            self._summary.config(text=(
                f"Events: {s['waiting']} waiting, {s['dead_lettered']} dead-lettered, "
                f"{s['delivered']} delivered.   Lifecycle actions: {s['actions_pending']} "
                f"pending, {s['actions_failed']} failed, {s['actions_completed']} completed."))
            rows = []
            for state in ("dead", "waiting"):
                rows += [(e["event_id"], state, e["event_name"], e["aggregate_id"],
                          e["attempts"], str(e["available_at"])[:19], e["last_error"] or "")
                         for e in outbox_dispatcher.events(state)]
            _fill(self._events, rows)
            _fill(self._actions, [
                (a["action_id"], a["student_id"], a["target_system"], a["action"],
                 a["status"], a["attempts"], a["last_error"] or "")
                for a in outbox_dispatcher.lifecycle_actions()])
            on = data_lifecycle_store.settings()
            from education_system.systems.university.domains.governance.application.data_lifecycle import (  # noqa: E501
                UNIVERSITY_POLICIES,
            )
            _fill(self._retention, [
                (t, "on" if on[t] else "off", len(data_lifecycle_store.due(t)),
                 f"{UNIVERSITY_POLICIES[t].period.days // 365} years",
                 UNIVERSITY_POLICIES[t].disposition.value) for t in RETENTION_TYPES])
        except Exception as exc:
            logger.exception("Connectors window refresh failed")
            messagebox.showerror(TITLE, f"Could not load:\n{exc}", parent=self)

    def _selected(self, tree, column=0):
        sel = tree.focus()
        return tree.item(sel, "values")[column] if sel else None

    # ── connectors ──────────────────────────────────────────────────────

    def _current(self, name):
        return next(c for c in connectors.overview() if c["connector_name"] == name)

    def configure(self):
        name = self._selected(self._connectors)
        if not name:
            messagebox.showwarning(TITLE, "Select a connector first.", parent=self)
            return
        current = self._current(name)["config"]
        transport = simpledialog.askstring(
            "Configure", f"{name}: transport (file / http):",
            initialvalue=current.get("transport", "file"), parent=self)
        if not transport:
            return
        transport = transport.strip().lower()
        config = {"transport": transport}
        if transport == "http":
            endpoint = simpledialog.askstring("Configure", "HTTPS endpoint:",
                                              initialvalue=current.get("endpoint", ""),
                                              parent=self)
            if not endpoint or not endpoint.strip().lower().startswith("https://"):
                messagebox.showerror("Configure", "The endpoint must start with https://",
                                     parent=self)
                return
            config["endpoint"] = endpoint.strip()
            token_env = simpledialog.askstring(
                "Configure", "Environment variable holding the token\n"
                             "(leave blank to name a file under var/secrets instead):",
                initialvalue=current.get("token_env", ""), parent=self)
            if token_env and token_env.strip():
                config["token_env"] = token_env.strip()
            else:
                token_file = simpledialog.askstring(
                    "Configure", "Token file under var/secrets (blank: no token):",
                    initialvalue=current.get("token_file", ""), parent=self)
                if token_file and token_file.strip():
                    config["token_file"] = token_file.strip()
        elif transport != "file":
            messagebox.showerror("Configure", "Transport must be file or http.", parent=self)
            return
        enabled = messagebox.askyesno("Configure", f"Switch {name} on now?", parent=self)
        connectors.configure(name, config, enabled=enabled)
        self.refresh()

    def set_enabled(self, enabled):
        name = self._selected(self._connectors)
        if not name:
            messagebox.showwarning(TITLE, "Select a connector first.", parent=self)
            return
        config = self._current(name)["config"] or {"transport": "file"}
        connectors.configure(name, config, enabled=enabled)
        self.refresh()

    def show_receipts(self):
        name = self._selected(self._connectors)
        if not name:
            messagebox.showwarning(TITLE, "Select a connector first.", parent=self)
            return
        rows = connectors.receipts(name, limit=40)
        text = "\n".join(f"{str(r['processed_at'])[:19]}  {r['external_reference'] or '-'}  "
                         f"{r['idempotency_key']}" for r in rows) or "Nothing sent yet."
        messagebox.showinfo(f"{name}: sent", text, parent=self)

    # ── queue ───────────────────────────────────────────────────────────

    def requeue(self):
        event_id = self._selected(self._events)
        if not event_id or self._selected(self._events, 1) != "dead":
            messagebox.showwarning(TITLE, "Select a dead-lettered event.", parent=self)
            return
        outbox_dispatcher.requeue(event_id)
        self.refresh()

    def run_now(self):
        result = outbox_dispatcher.run_once()
        self.refresh()
        messagebox.showinfo(TITLE, f"Outbox: {result.get('outbox', result)}\n"
                                   f"Lifecycle actions: {result.get('lifecycle_actions', '-')}",
                            parent=self)

    # ── retention ───────────────────────────────────────────────────────

    def set_retention(self, enabled):
        record_type = self._selected(self._retention)
        if not record_type:
            messagebox.showwarning(TITLE, "Select a record type first.", parent=self)
            return
        if enabled and not messagebox.askyesno(
                "Record retention",
                f"Turn on disposal for {record_type}?\n\nRecords past their period will be "
                "redacted at the next daily run. This cannot be undone.", parent=self):
            return
        data_lifecycle_store.set_enabled(record_type, enabled, actor_id=self._actor)
        self.refresh()


def main() -> None:
    from education_system.platform.delivery.gui.window_sizing import install
    from education_system.systems.university.shell.gui.auth.launch_guard import (
        require_launcher_auth,
    )

    user = require_launcher_auth(TITLE)
    if user is None:
        return
    if not sso_admin.is_admin(user):
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(TITLE, "Connector and event-queue management is admin only.")
        root.destroy()
        return
    install()
    root = tk.Tk()
    root.title(_t("gui.admin.connectors.title", default=TITLE))
    root.geometry("1400x900")
    root.minsize(1200, 800)
    ConnectorsApp(root, user=user).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
