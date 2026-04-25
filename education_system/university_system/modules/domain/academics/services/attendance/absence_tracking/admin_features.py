"""
Admin features for the Absence Tracker.

Fifty admin utilities organised into service classes by domain:

    AttendanceDataService     #1–7    bulk import/export, edit, undo, dedupe
    RequestWorkflowService    #8–13   bulk decisions, attachments, templates
    PolicyService             #14–18  per-module / default policy, statuses
    ReportingService          #19–26  at-risk, trends, scheduled reports
    NotificationService       #27–30  threshold alerts, bulk announcements
    IntegrationService        #31–37  calendar, risk feed, finance, etc.
    BulkOperationsService     #38–41  whole-class roll, copy day, recurring
    SecurityAuditService      #42–46  permissions, audit, GDPR, retention
    DiagnosticsService        #47–50  orphan rows, DB health, mismatches

Plus shared infrastructure (kept as module-level so student_features,
staff_features, and absence_tracker can import the same names):

    AdminContext, safe, audit, ensure_support_tables, install_soft_delete
    _combo_dialog, _show_table, _report_window
    _rows_to_txt, _rows_to_pdf, _email_admin, _export_rows_to_csv
    _get_setting, _set_setting
    pick_date, pick_date_range
    build_admin_tab

Logging is routed through ``infrastructure.logging.log_config.configure_logging``
so all output lands in ``university_system/logs/app.log`` with the rest of
the system. Every state-changing DB operation is wrapped in
``try/except sqlite3.Error`` with explicit ``rollback()`` and a friendly
dialog so a single bad row never leaves the connection half-committed.
"""

from __future__ import annotations

import calendar as _cal
import csv
import functools
import json
import logging
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Iterable, Optional

# Route through the central rotating file handler (logs/app.log) so this
# module's output joins every other subsystem's. Falls back to stderr-only
# if log_config can't be imported (e.g. partial install).
try:
    from education_system.university_system.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="absence_tracker.admin")
except Exception:  # pragma: no cover
    logger = logging.getLogger("absence_tracker.admin")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)


# ===========================================================================
# Context + decorators + audit helper
# ===========================================================================

@dataclass
class AdminContext:
    """Lightweight bag passed into every admin feature."""
    db: Any
    parent: tk.Misc
    user: dict

    @property
    def uid(self) -> Optional[int]:
        v = self.user.get("id")
        return int(v) if v is not None else None

    @property
    def username(self) -> str:
        return str(self.user.get("username") or "")


def audit(ctx: AdminContext, action: str, target: str = "",
          target_id: Any = "", details: str = "") -> None:
    """Write a row to the admin audit table. Never raises."""
    try:
        ctx.db.cur.execute(
            """INSERT INTO abs_tracker_audit
               (user_id, username, action, target, target_id, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ctx.user.get("id"), ctx.user.get("username"),
             action, target, str(target_id), details))
        ctx.db.conn.commit()
    except sqlite3.Error:
        logger.exception("audit write failed for action=%s", action)


def safe(title: str = "Error") -> Callable:
    """Decorator: logs + shows a friendly error dialog on any exception."""
    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapped(ctx_or_self, *args, **kwargs):
            # Resolve the user for the start log line whether the call was
            # `fn(ctx, ...)` (legacy module-level functions) or
            # `method(self, ctx, ...)` (service methods bound through the
            # legacy aliases).
            if isinstance(ctx_or_self, AdminContext):
                username = ctx_or_self.user.get("username")
            elif args and isinstance(args[0], AdminContext):
                username = args[0].user.get("username")
            else:
                ctx = getattr(ctx_or_self, "ctx", None)
                username = ctx.user.get("username") if ctx else "?"
            try:
                logger.info("▶ %s user=%s", fn.__name__, username)
                out = fn(ctx_or_self, *args, **kwargs)
                logger.info("✓ %s", fn.__name__)
                return out
            except Exception as e:
                logger.exception("✗ %s failed", fn.__name__)
                # Resolve a parent window for the error dialog.
                parent = None
                if isinstance(ctx_or_self, AdminContext):
                    parent = ctx_or_self.parent
                elif args and isinstance(args[0], AdminContext):
                    parent = args[0].parent
                else:
                    ctx = getattr(ctx_or_self, "ctx", None)
                    parent = ctx.parent if ctx else None
                try:
                    messagebox.showerror(
                        title, f"{fn.__name__} failed:\n{e}", parent=parent)
                except Exception:
                    pass
        return wrapped
    return deco


# ===========================================================================
# Support tables
# ===========================================================================

def ensure_support_tables(db) -> None:
    """Create all support tables used by the admin features if missing."""
    cur = db.cur
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS abs_tracker_audit (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT DEFAULT CURRENT_TIMESTAMP,
            user_id     INTEGER, username TEXT,
            action      TEXT, target TEXT, target_id TEXT, details TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_trash (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            deleted_at     TEXT DEFAULT CURRENT_TIMESTAMP,
            deleted_by     TEXT,
            original_table TEXT, original_id INTEGER, payload TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_settings (
            key   TEXT PRIMARY KEY, value TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_module_policy (
            module_code      TEXT PRIMARY KEY,
            min_percent      REAL,
            late_as_absent   INTEGER, grace_minutes INTEGER, notes TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_statuses (
            code TEXT PRIMARY KEY, label TEXT, counts_as TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_auto_excuse_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT, status TEXT DEFAULT 'excused',
            enabled INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_request_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER, file_path TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_request_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER, author TEXT, body TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_request_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE, body TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_delegations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user INTEGER, to_user INTEGER,
            active_from TEXT, active_to TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_scheduled_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, frequency TEXT, recipients TEXT,
            report_type TEXT, last_run TEXT, enabled INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_retention (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy TEXT, years INTEGER, applied_at TEXT
        );
    """)
    cur.executemany(
        "INSERT OR IGNORE INTO abs_tracker_statuses (code, label, counts_as) VALUES (?,?,?)",
        [("present", "Present", "present"),
         ("absent",  "Absent",  "absent"),
         ("late",    "Late",    "late"),
         ("excused", "Excused", "excused")])
    db.conn.commit()


# ===========================================================================
# Settings + dialog helpers (module-level, public API)
# ===========================================================================

def _get_setting(db, key, default=None):
    try:
        r = db.cur.execute(
            "SELECT value FROM abs_tracker_settings WHERE key=?",
            (key,)).fetchone()
        return r[0] if r else default
    except sqlite3.Error:
        logger.exception("get_setting failed key=%s", key)
        return default


def _set_setting(db, key, value):
    try:
        db.cur.execute(
            "INSERT OR REPLACE INTO abs_tracker_settings (key, value) VALUES (?, ?)",
            (key, str(value)))
        db.conn.commit()
    except sqlite3.Error:
        db.conn.rollback()
        logger.exception("set_setting failed key=%s", key)
        raise


def _combo_dialog(parent, title, label, values) -> Optional[str]:
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent)
    dlg.grab_set()
    dlg.geometry("520x140")
    tk.Label(dlg, text=label).pack(pady=8)
    var = tk.StringVar()
    cb = ttk.Combobox(dlg, textvariable=var, values=values,
                      state="readonly", width=60)
    cb.pack(padx=10)
    result = {"v": None}

    def ok():
        result["v"] = var.get()
        dlg.destroy()

    tk.Button(dlg, text="OK", command=ok, bg="#2563eb", fg="white",
              relief="flat", padx=16, pady=4).pack(pady=12)
    dlg.wait_window()
    return result["v"] or None


def _show_table(parent, title, columns, rows, widths=None, extra_button=None):
    """Pop up a modal window showing `rows` in a Treeview."""
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("1000x600")
    frame = ttk.Frame(win)
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    tree = ttk.Treeview(frame, columns=columns, show="headings")
    widths = widths or [max(80, int(900 / max(1, len(columns))))] * len(columns)
    for c, w in zip(columns, widths):
        tree.heading(c, text=c)
        tree.column(c, width=w, anchor="w")
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    for row in rows:
        tree.insert("", "end", values=row)
    btns = tk.Frame(win)
    btns.pack(fill="x", pady=6)
    if extra_button:
        label, cmd = extra_button
        tk.Button(btns, text=label, command=cmd, bg="#2563eb", fg="white",
                  relief="flat", padx=10, pady=4).pack(side="left", padx=10)
    tk.Button(btns, text="Close", command=win.destroy, bg="#6b7280",
              fg="white", relief="flat", padx=10, pady=4
              ).pack(side="right", padx=10)
    return win, tree


def pick_date(parent, title="Pick a date",
              initial: Optional[date] = None) -> Optional[str]:
    """Modal year/month/day combobox dialog. Returns 'YYYY-MM-DD' or None."""
    today = initial or date.today()
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent)
    dlg.grab_set()
    dlg.geometry("360x180")
    tk.Label(dlg, text=title, font=("Arial", 11, "bold")).pack(pady=10)

    row = tk.Frame(dlg); row.pack(pady=6)
    years = [str(y) for y in range(today.year - 2, today.year + 4)]
    months = [f"{m:02d}" for m in range(1, 13)]
    y_var = tk.StringVar(value=str(today.year))
    m_var = tk.StringVar(value=f"{today.month:02d}")
    d_var = tk.StringVar(value=f"{today.day:02d}")

    def days_for(y: str, m: str) -> list[str]:
        try:
            n = _cal.monthrange(int(y), int(m))[1]
        except (ValueError, _cal.IllegalMonthError):
            n = 31
        return [f"{d:02d}" for d in range(1, n + 1)]

    tk.Label(row, text="Year").grid(row=0, column=0, padx=4)
    tk.Label(row, text="Month").grid(row=0, column=1, padx=4)
    tk.Label(row, text="Day").grid(row=0, column=2, padx=4)
    y_cb = ttk.Combobox(row, textvariable=y_var, values=years,
                        width=6, state="readonly")
    m_cb = ttk.Combobox(row, textvariable=m_var, values=months,
                        width=5, state="readonly")
    d_cb = ttk.Combobox(row, textvariable=d_var,
                        values=days_for(y_var.get(), m_var.get()),
                        width=5, state="readonly")
    y_cb.grid(row=1, column=0, padx=4)
    m_cb.grid(row=1, column=1, padx=4)
    d_cb.grid(row=1, column=2, padx=4)

    def refresh_days(*_):
        days = days_for(y_var.get(), m_var.get())
        d_cb.configure(values=days)
        if d_var.get() not in days:
            d_var.set(days[-1])

    y_var.trace_add("write", refresh_days)
    m_var.trace_add("write", refresh_days)

    result = {"v": None}

    def ok():
        result["v"] = f"{y_var.get()}-{m_var.get()}-{d_var.get()}"
        dlg.destroy()

    btns = tk.Frame(dlg); btns.pack(pady=12)
    tk.Button(btns, text="OK", command=ok, bg="#2563eb", fg="white",
              relief="flat", padx=18, pady=4).pack(side="left", padx=6)
    tk.Button(btns, text="Cancel", command=dlg.destroy, bg="#6b7280",
              fg="white", relief="flat", padx=18, pady=4
              ).pack(side="left", padx=6)
    dlg.wait_window()
    return result["v"]


def pick_date_range(parent,
                    title="Pick a date range") -> Optional[tuple[str, str]]:
    """Two sequential date pickers. Returns (start, end) or None."""
    start = pick_date(parent, f"{title} — start date")
    if not start:
        return None
    try:
        init = datetime.strptime(start, "%Y-%m-%d").date()
    except ValueError:
        init = None
    end = pick_date(parent, f"{title} — end date", initial=init)
    if not end:
        return None
    if end < start:
        start, end = end, start
    return start, end


def _export_rows_to_csv(rows: Iterable, headers: Iterable[str],
                        parent) -> Optional[str]:
    path = filedialog.asksaveasfilename(
        parent=parent, defaultextension=".csv",
        filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
    if not path:
        return None
    try:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(list(headers))
            w.writerows(rows)
    except OSError:
        logger.exception("CSV export failed path=%s", path)
        messagebox.showerror("Save failed",
                             "Could not write CSV (see log).",
                             parent=parent)
        return None
    return path


# ===========================================================================
# Email + report rendering helpers (kept module-level — used by other modules)
# ===========================================================================

def _email_admin(db, subject: str, body: str,
                 sender_username: str = "") -> int:
    """Deliver the report to admin/superadmin in-app inboxes.

    Writes to ``messages`` (the inbox), ``stored_emails`` (sent archive),
    and ``email_log`` (audit), and tries SMTP via the shared helper as a
    secondary channel. Returns the number of inboxes delivered to.
    """
    try:
        admins = db.cur.execute(
            "SELECT id, username, email FROM users "
            "WHERE role IN ('admin','superadmin') "
            "  AND email IS NOT NULL AND TRIM(email) <> ''").fetchall()
    except sqlite3.Error:
        logger.exception("admin lookup failed")
        return 0
    if not admins:
        return 0

    # Resolve a sender_id for messages.sender_id.
    sender_id = None
    if sender_username:
        try:
            r = db.cur.execute(
                "SELECT id FROM users WHERE username = ?",
                (sender_username,)).fetchone()
            sender_id = r[0] if r else None
        except sqlite3.Error:
            logger.exception("sender lookup failed username=%s", sender_username)
    if sender_id is None:
        try:
            r = db.cur.execute(
                "SELECT id FROM users WHERE role IN ('admin','superadmin') "
                "LIMIT 1").fetchone()
            sender_id = r[0] if r else admins[0][0]
        except sqlite3.Error:
            sender_id = admins[0][0]

    body_tagged = (f"[Absence Tracker report — from "
                   f"{sender_username or 'absence_tracker'}]\n\n{body}")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        msg_cols = {r[1] for r in db.cur.execute(
            "PRAGMA table_info(messages)").fetchall()}
        se_cols = {r[1] for r in db.cur.execute(
            "PRAGMA table_info(stored_emails)").fetchall()}
        el_cols = {r[1] for r in db.cur.execute(
            "PRAGMA table_info(email_log)").fetchall()}
    except sqlite3.Error:
        logger.exception("schema probe failed")
        msg_cols = se_cols = el_cols = set()

    try:
        from education_system.university_system.infrastructure.email import (
            send_email,
        )
    except Exception:
        send_email = None

    n = 0
    for rid, _uname, addr in admins:
        # --- in-app inbox ---
        cols = ["sender_id", "recipient_id", "subject"]
        vals: list = [sender_id, rid, subject]
        if "message" in msg_cols:
            cols.append("message"); vals.append(body_tagged)
        if "content" in msg_cols:
            cols.append("content"); vals.append(body_tagged)
        if "is_read" in msg_cols:
            cols.append("is_read"); vals.append(0)
        if "sent_at" in msg_cols:
            cols.append("sent_at"); vals.append(now)
        try:
            db.cur.execute(
                f"INSERT INTO messages ({', '.join(cols)}) "
                f"VALUES ({', '.join('?' * len(cols))})", vals)
            n += 1
        except sqlite3.Error:
            logger.exception("messages insert failed for %s", addr)
            continue

        # --- sent archive ---
        if se_cols:
            se_vals = {
                "recipient_email": addr, "subject": subject,
                "body": body_tagged,
                "sender_email": "noreply@absence-tracker",
                "sender_name": sender_username or "Absence Tracker",
                "created_date": now, "sent_date": now, "status": "sent",
            }
            usable = [k for k in se_vals if k in se_cols]
            if usable:
                try:
                    db.cur.execute(
                        f"INSERT INTO stored_emails ({', '.join(usable)}) "
                        f"VALUES ({', '.join('?' * len(usable))})",
                        [se_vals[k] for k in usable])
                except sqlite3.Error:
                    logger.debug("stored_emails insert skipped",
                                 exc_info=True)

        # --- audit log ---
        if el_cols:
            el_vals = {
                "recipient": addr, "subject": subject,
                "message": body_tagged, "sent_date": now, "status": "sent",
                "related_to": "absence_tracker",
                "sender_name": sender_username or "absence_tracker",
                "sender_email": "noreply@absence-tracker",
            }
            usable = [k for k in el_vals if k in el_cols]
            if usable:
                try:
                    db.cur.execute(
                        f"INSERT INTO email_log ({', '.join(usable)}) "
                        f"VALUES ({', '.join('?' * len(usable))})",
                        [el_vals[k] for k in usable])
                except sqlite3.Error:
                    logger.debug("email_log insert skipped", exc_info=True)

        # --- best-effort SMTP ---
        if send_email is not None:
            try:
                send_email(recipient=addr, subject=subject, body=body_tagged)
            except Exception:
                logger.debug("send_email skipped/failed for %s",
                             addr, exc_info=True)

    try:
        db.conn.commit()
    except sqlite3.Error:
        db.conn.rollback()
        logger.exception("email_admin commit failed")
        return 0
    return n


def _rows_to_txt(columns, rows) -> str:
    """Render rows as an aligned plain-text table."""
    cols = [str(c) for c in columns]
    data = [[str(x) if x is not None else "" for x in r] for r in rows]
    widths = [max(len(c), *(len(row[i]) for row in data)) if data else len(c)
              for i, c in enumerate(cols)]
    sep = "  ".join("-" * w for w in widths)
    lines = ["  ".join(c.ljust(widths[i]) for i, c in enumerate(cols)), sep]
    for row in data:
        lines.append("  ".join(row[i].ljust(widths[i])
                               for i in range(len(cols))))
    return "\n".join(lines)


def _rows_to_pdf(path, title, columns, rows) -> None:
    """Write rows to a simple landscape A4 PDF using reportlab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )
    doc = SimpleDocTemplate(path, pagesize=landscape(A4),
                            leftMargin=30, rightMargin=30,
                            topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Heading1"]), Spacer(1, 10)]
    data = [list(columns)] + [
        ["" if x is None else str(x) for x in r] for r in rows
    ]
    tbl = Table(data, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("GRID",       (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.whitesmoke, colors.white]),
    ]))
    story.append(tbl)
    doc.build(story)


def _report_window(parent, title, columns, rows, *,
                   db=None, user=None, widths=None):
    """Open a report in its own window with CSV/TXT/PDF/Email/Close toolbar."""
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("1024x640")

    top = ttk.Frame(win)
    top.pack(fill="both", expand=True, padx=10, pady=(10, 4))
    tree = ttk.Treeview(top, columns=columns, show="headings")
    widths = widths or [max(80, int(980 / max(1, len(columns))))] * len(columns)
    for c, w in zip(columns, widths):
        tree.heading(c, text=c)
        tree.column(c, width=w, anchor="w")
    vsb = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    for r in rows:
        tree.insert("", "end", values=r)

    def _suggested(ext: str) -> str:
        safe_title = "".join(c if c.isalnum() else "_" for c in title)
        return f"{safe_title}.{ext}"

    def save_csv():
        path = filedialog.asksaveasfilename(
            parent=win, defaultextension=".csv",
            initialfile=_suggested("csv"),
            filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh); w.writerow(columns); w.writerows(rows)
        except OSError as e:
            logger.exception("save_csv failed")
            messagebox.showerror("Error", str(e), parent=win)
            return
        messagebox.showinfo("Saved", f"CSV saved:\n{path}", parent=win)

    def save_txt():
        path = filedialog.asksaveasfilename(
            parent=win, defaultextension=".txt",
            initialfile=_suggested("txt"),
            filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(title + "\n" + ("=" * len(title)) + "\n\n")
                fh.write(_rows_to_txt(columns, rows))
        except OSError as e:
            logger.exception("save_txt failed")
            messagebox.showerror("Error", str(e), parent=win)
            return
        messagebox.showinfo("Saved", f"Text saved:\n{path}", parent=win)

    def save_pdf():
        path = filedialog.asksaveasfilename(
            parent=win, defaultextension=".pdf",
            initialfile=_suggested("pdf"),
            filetypes=[("PDF", "*.pdf"), ("All", "*.*")])
        if not path:
            return
        try:
            _rows_to_pdf(path, title, columns, rows)
        except Exception as e:  # reportlab raises bare Exception in places
            logger.exception("save_pdf failed")
            messagebox.showerror("Error",
                                 f"PDF export failed:\n{e}\n\n"
                                 "(reportlab required)", parent=win)
            return
        messagebox.showinfo("Saved", f"PDF saved:\n{path}", parent=win)

    def email_admin():
        if db is None:
            messagebox.showerror("Unavailable",
                                 "Email option requires a DB context.",
                                 parent=win)
            return
        try:
            body = _rows_to_txt(columns, rows)
            subject = f"[Absence Tracker] {title}"
            n = _email_admin(db, subject, body,
                             (user or {}).get("username", ""))
        except Exception as e:
            logger.exception("email_admin failed")
            messagebox.showerror("Error", str(e), parent=win)
            return
        messagebox.showinfo("Queued",
                            f"Emailed {n} admin recipient(s).",
                            parent=win)

    bar = tk.Frame(win); bar.pack(fill="x", padx=10, pady=8)
    for label, cmd, bg in [
        ("💾 Save CSV", save_csv, "#16a34a"),
        ("📝 Save TXT", save_txt, "#16a34a"),
        ("📄 Save PDF", save_pdf, "#16a34a"),
        ("✉ Email admin", email_admin, "#2563eb"),
    ]:
        tk.Button(bar, text=label, command=cmd, bg=bg, fg="white",
                  relief="flat", padx=12, pady=6).pack(side="left", padx=4)
    tk.Button(bar, text="Close", command=win.destroy, bg="#6b7280",
              fg="white", relief="flat", padx=12, pady=6
              ).pack(side="right", padx=4)
    return win


# ===========================================================================
# Validated input + entity pickers (classes)
# ===========================================================================

class Prompt:
    """Reusable Tk dialogs with validation."""

    @staticmethod
    def iso_date(parent, title: str = "Date",
                 prompt: str = "Date (YYYY-MM-DD):",
                 initial: Optional[str] = None) -> Optional[str]:
        initial = initial or date.today().isoformat()
        while True:
            s = simpledialog.askstring(title, prompt, parent=parent,
                                       initialvalue=initial)
            if s is None:
                return None
            s = s.strip()
            try:
                datetime.strptime(s, "%Y-%m-%d")
                return s
            except ValueError:
                messagebox.showerror("Bad date",
                                     f"'{s}' is not YYYY-MM-DD.",
                                     parent=parent)
                initial = s

    @staticmethod
    def non_empty(parent, title: str, prompt: str,
                  min_len: int = 1) -> Optional[str]:
        while True:
            s = simpledialog.askstring(title, prompt, parent=parent)
            if s is None:
                return None
            s = s.strip()
            if len(s) >= min_len:
                return s
            messagebox.showerror("Too short",
                                 f"Please give at least {min_len} character(s).",
                                 parent=parent)

    @staticmethod
    def confirm(parent, title: str, msg: str) -> bool:
        return bool(messagebox.askyesno(title, msg, parent=parent))


class StudentPicker:
    """Pick a student id from the users table."""

    def __init__(self, ctx: AdminContext) -> None:
        self.ctx = ctx

    def pick(self, prompt: str = "Pick a student") -> Optional[str]:
        try:
            rows = self.ctx.db.get_users("student")
        except Exception:
            logger.exception("get_users('student') failed")
            messagebox.showerror("Error", "Could not load students.",
                                 parent=self.ctx.parent)
            return None
        if not rows:
            messagebox.showinfo("No students",
                                "No students in the database.",
                                parent=self.ctx.parent)
            return None
        options = {f"{r[3] or r[1]} ({r[1]})": r[0] for r in rows}
        pick = _combo_dialog(self.ctx.parent, prompt,
                             "Student:", list(options.keys()))
        return options.get(pick) if pick else None


class ModulePicker:
    """Pick a module code from the modules table."""

    def __init__(self, ctx: AdminContext) -> None:
        self.ctx = ctx

    def pick(self, prompt: str = "Pick a module") -> Optional[str]:
        try:
            rows = self.ctx.db.get_courses()
        except Exception:
            logger.exception("get_courses failed")
            messagebox.showerror("Error", "Could not load modules.",
                                 parent=self.ctx.parent)
            return None
        if not rows:
            messagebox.showinfo("No modules",
                                "No modules in the database.",
                                parent=self.ctx.parent)
            return None
        options = {f"{r[1]} - {r[2]}": r[0] for r in rows}
        pick = _combo_dialog(self.ctx.parent, prompt,
                             "Module:", list(options.keys()))
        return options.get(pick) if pick else None


# Legacy single-call wrappers retained so old code paths still work.
def _pick_student(ctx: AdminContext,
                  prompt: str = "Pick a student") -> Optional[str]:
    return StudentPicker(ctx).pick(prompt)


def _pick_module(ctx: AdminContext,
                 prompt: str = "Pick a module") -> Optional[str]:
    return ModulePicker(ctx).pick(prompt)


# ===========================================================================
# AttendanceDataService — features #1–#7
# ===========================================================================

class AttendanceDataService:
    """Bulk import/export, edit, undo-delete, dedupe, audit, lock past."""

    def __init__(self, ctx: AdminContext, module_picker: ModulePicker
                 ) -> None:
        self.ctx = ctx
        self.module_picker = module_picker

    # --- #1 -----------------------------------------------------------
    @safe("Bulk import")
    def bulk_import_csv(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.ctx.parent,
            filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if not path:
            return
        if not Path(path).is_file():
            messagebox.showerror("Missing", f"File not found:\n{path}",
                                 parent=self.ctx.parent)
            return
        ok = bad = 0
        try:
            with open(path, encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                required = {"student_id", "module_code", "date", "status"}
                missing = required - set(reader.fieldnames or [])
                if missing:
                    messagebox.showerror(
                        "Bad header",
                        f"Missing column(s): {', '.join(sorted(missing))}",
                        parent=self.ctx.parent)
                    return
                for row in reader:
                    try:
                        self.ctx.db.record_absence(
                            row["student_id"].strip(),
                            row["module_code"].strip(),
                            row["date"].strip(),
                            row["status"].strip(),
                            (row.get("reason") or "").strip())
                        ok += 1
                    except (sqlite3.Error, KeyError, ValueError) as e:
                        logger.warning("import row %s failed: %s", row, e)
                        bad += 1
            self.ctx.db.conn.commit()
        except OSError as e:
            logger.exception("bulk import open failed path=%s", path)
            messagebox.showerror("Read failed", str(e),
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "bulk_import", "attendance", "",
              f"ok={ok} bad={bad} file={path}")
        messagebox.showinfo("Import complete",
                            f"Imported {ok} rows. {bad} rejected.",
                            parent=self.ctx.parent)

    # --- #2 -----------------------------------------------------------
    @safe("Bulk export")
    def bulk_export_csv(self) -> None:
        try:
            rows = self.ctx.db.get_absences()
        except Exception:
            logger.exception("bulk_export get_absences failed")
            messagebox.showerror("Error", "Could not load attendance.",
                                 parent=self.ctx.parent)
            return
        headers = ("id", "student", "module_code", "module_name",
                   "date", "status", "reason")
        path = _export_rows_to_csv(rows, headers, self.ctx.parent)
        if path:
            audit(self.ctx, "bulk_export", "attendance", "",
                  f"rows={len(rows)} file={path}")
            messagebox.showinfo("Exported",
                                f"Wrote {len(rows)} rows to:\n{path}",
                                parent=self.ctx.parent)

    # --- #3 -----------------------------------------------------------
    @safe("Edit record")
    def edit_attendance_row(self) -> None:
        rid = simpledialog.askinteger("Edit", "Attendance row id:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        try:
            old = self.ctx.db.cur.execute(
                "SELECT status, reason FROM attendance WHERE id=?",
                (rid,)).fetchone()
        except sqlite3.Error:
            logger.exception("attendance lookup failed rid=%s", rid)
            messagebox.showerror("Error", "Could not load row.",
                                 parent=self.ctx.parent)
            return
        if not old:
            messagebox.showerror("Not found", f"No row {rid}",
                                 parent=self.ctx.parent)
            return
        valid_statuses = ["present", "absent", "late", "excused"]
        new_status = _combo_dialog(
            self.ctx.parent, "Status",
            f"New status (was {old[0]}):",
            valid_statuses) or old[0]
        new_reason = simpledialog.askstring(
            "Reason", f"New reason (was {old[1] or ''}):",
            parent=self.ctx.parent) or old[1]
        try:
            self.ctx.db.cur.execute(
                "UPDATE attendance SET status=?, reason=? WHERE id=?",
                (new_status, new_reason, rid))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("attendance update failed rid=%s", rid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "edit_record", "attendance", rid,
              f"{old[0]}→{new_status}")
        messagebox.showinfo("Saved", "Record updated.",
                            parent=self.ctx.parent)

    # --- #4 -----------------------------------------------------------
    @safe("Undo delete")
    def undo_recent_deletes(self) -> None:
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT id, deleted_at, deleted_by, original_table, payload
                   FROM abs_tracker_trash WHERE deleted_at >= ?
                   ORDER BY deleted_at DESC""", (cutoff,)).fetchall()
        except sqlite3.Error:
            logger.exception("trash fetch failed")
            messagebox.showerror("Error", "Could not load trash.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("Trash empty",
                                "Nothing deleted in the last 24h.",
                                parent=self.ctx.parent)
            return

        def restore_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Select", "Pick row(s) to restore.",
                                    parent=win)
                return
            restored = 0
            try:
                for item in sel:
                    v = tree.item(item)["values"]
                    p = json.loads(v[4])
                    self.ctx.db.cur.execute(
                        """INSERT INTO attendance
                           (id, student_id, module_code, date, status, reason)
                           VALUES (?,?,?,?,?,?)""",
                        (p["id"], p["student_id"], p["module_code"],
                         p["date"], p["status"], p["reason"]))
                    self.ctx.db.cur.execute(
                        "DELETE FROM abs_tracker_trash WHERE id=?", (v[0],))
                    restored += 1
                self.ctx.db.conn.commit()
            except (sqlite3.Error, json.JSONDecodeError, KeyError) as e:
                self.ctx.db.conn.rollback()
                logger.exception("undo restore failed")
                messagebox.showerror("Failed", str(e), parent=win)
                return
            audit(self.ctx, "undo_delete", "attendance", "",
                  f"rows={restored}")
            messagebox.showinfo("Restored",
                                f"Restored {restored} row(s).", parent=win)
            win.destroy()

        win, tree = _show_table(
            self.ctx.parent, "Trash (24h)",
            ("id", "deleted_at", "deleted_by", "table", "payload"),
            rows, extra_button=("Restore selected", restore_selected))

    # --- #5 -----------------------------------------------------------
    @safe("Merge duplicates")
    def merge_duplicate_rows(self) -> None:
        try:
            dups = self.ctx.db.cur.execute(
                """SELECT student_id, module_code, date, COUNT(*) c,
                          MIN(id), MAX(id)
                   FROM attendance
                   GROUP BY student_id, module_code, date
                   HAVING c > 1""").fetchall()
        except sqlite3.Error:
            logger.exception("dup scan failed")
            messagebox.showerror("Error", "Could not scan for duplicates.",
                                 parent=self.ctx.parent)
            return
        if not dups:
            messagebox.showinfo("No duplicates",
                                "No duplicate rows found.",
                                parent=self.ctx.parent)
            return
        if not Prompt.confirm(
                self.ctx.parent, "Confirm dedupe",
                f"Found {len(dups)} duplicate group(s).\n"
                "Keep the earliest row per (student, module, date) and "
                "delete the rest?"):
            return
        removed = 0
        try:
            for sid, mod, d, _c, keep_id, _max in dups:
                cur = self.ctx.db.cur.execute(
                    """DELETE FROM attendance
                       WHERE student_id=? AND module_code=? AND date=?
                         AND id<>?""", (sid, mod, d, keep_id))
                removed += cur.rowcount
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("dedupe delete failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "merge_duplicates", "attendance", "",
              f"removed={removed}")
        messagebox.showinfo("Merged",
                            f"Removed {removed} duplicate row(s); "
                            "kept earliest per day.",
                            parent=self.ctx.parent)

    # --- #6 -----------------------------------------------------------
    @safe("Audit log")
    def show_correction_audit(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT ts, username, action, target, target_id, details
                   FROM abs_tracker_audit
                   ORDER BY ts DESC LIMIT 500""").fetchall()
        except sqlite3.Error:
            logger.exception("audit fetch failed")
            rows = []
        _show_table(self.ctx.parent, "Audit log (last 500)",
                    ("when", "user", "action", "target", "target_id", "details"),
                    rows, widths=[150, 120, 140, 100, 100, 380])

    # --- #7 -----------------------------------------------------------
    @safe("Lock past dates")
    def lock_past_dates(self) -> None:
        days = simpledialog.askinteger(
            "Lock past dates",
            "Lock edits to records older than how many days?",
            parent=self.ctx.parent, minvalue=0, maxvalue=3650)
        if days is None:
            return
        days = int(days)  # defensive: enforce integer for the trigger DDL
        try:
            _set_setting(self.ctx.db, "lock_days", days)
            self.ctx.db.cur.executescript(f"""
                DROP TRIGGER IF EXISTS abs_lock_update;
                CREATE TRIGGER abs_lock_update
                BEFORE UPDATE ON attendance
                FOR EACH ROW
                WHEN julianday('now') - julianday(OLD.date) > {days}
                BEGIN
                  SELECT RAISE(ABORT, 'Attendance row older than lock window');
                END;
            """)
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("lock trigger install failed days=%s", days)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "lock_past_dates", "settings", "lock_days", str(days))
        messagebox.showinfo("Locked",
                            f"Records older than {days} day(s) "
                            "are now read-only.",
                            parent=self.ctx.parent)


# ===========================================================================
# RequestWorkflowService — features #8–#13
# ===========================================================================

class RequestWorkflowService:
    """Bulk approve/reject, attachments, expire, delegate, comments,
    templates."""

    def __init__(self, ctx: AdminContext, module_picker: ModulePicker
                 ) -> None:
        self.ctx = ctx
        self.module_picker = module_picker

    # --- #8 -----------------------------------------------------------
    @safe("Bulk approve")
    def bulk_approve_or_reject(self) -> None:
        mod = self.module_picker.pick(
            "Limit to module (Cancel = all modules)") or None
        action = _combo_dialog(self.ctx.parent, "Decide",
                               "Action for all pending:",
                               ["approved", "rejected"])
        if not action:
            return
        q = ("SELECT id, student_id, module_code, date, reason "
             "FROM absence_requests WHERE status='pending'")
        p: list = []
        if mod:
            q += " AND module_code=?"
            p.append(mod)
        try:
            pending = self.ctx.db.cur.execute(q, p).fetchall()
        except sqlite3.Error:
            logger.exception("pending fetch failed")
            messagebox.showerror("Error", "Could not load pending requests.",
                                 parent=self.ctx.parent)
            return
        if not pending:
            messagebox.showinfo("None", "No pending requests match.",
                                parent=self.ctx.parent)
            return
        if not Prompt.confirm(
                self.ctx.parent, "Confirm bulk decision",
                f"{action.title()} {len(pending)} request(s)?"):
            return
        try:
            for rid, sid, mc, d, reason in pending:
                self.ctx.db.update_request(rid, action)
                if action == "approved":
                    self.ctx.db.record_absence(
                        sid, mc, d, "excused",
                        f"[Bulk-approved] {reason}")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("bulk decide failed action=%s", action)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "bulk_request_decide", "absence_requests", "",
              f"action={action} n={len(pending)}")
        messagebox.showinfo("Done",
                            f"{action.title()} {len(pending)} request(s).",
                            parent=self.ctx.parent)

    # --- #9 -----------------------------------------------------------
    @safe("Attach document")
    def attach_document_to_request(self) -> None:
        rid = simpledialog.askinteger("Attachment", "Request id:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        path = filedialog.askopenfilename(parent=self.ctx.parent)
        if not path:
            return
        p = Path(path)
        if not p.is_file():
            messagebox.showerror("Missing", f"File not found:\n{path}",
                                 parent=self.ctx.parent)
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_request_attachments
                   (request_id, file_path) VALUES (?,?)""",
                (rid, str(p.resolve())))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("attachment insert failed rid=%s", rid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "request_attach", "absence_requests", rid, p.name)
        messagebox.showinfo("Attached", f"Attached {p.name}.",
                            parent=self.ctx.parent)

    # --- #10 ----------------------------------------------------------
    @safe("Expire pending")
    def expire_old_pending_requests(self) -> None:
        days = simpledialog.askinteger(
            "Expire", "Expire pending older than (days)?",
            parent=self.ctx.parent, minvalue=1, maxvalue=365)
        if days is None:
            return
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        if not Prompt.confirm(
                self.ctx.parent, "Confirm",
                f"Reject every pending request older than {days} day(s)?"):
            return
        try:
            cur = self.ctx.db.cur.execute(
                """UPDATE absence_requests SET status='rejected'
                   WHERE status='pending' AND submitted_at < ?""",
                (cutoff,))
            n = cur.rowcount
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("expire pending failed days=%s", days)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "expire_pending", "absence_requests", "",
              f"cutoff={cutoff} n={n}")
        messagebox.showinfo("Expired",
                            f"Rejected {n} stale request(s).",
                            parent=self.ctx.parent)

    # --- #11 ----------------------------------------------------------
    @safe("Delegate approval")
    def delegate_approval_authority(self) -> None:
        try:
            staff = (self.ctx.db.get_users("staff")
                     + self.ctx.db.get_users("instructor"))
        except Exception:
            logger.exception("staff list fetch failed")
            messagebox.showerror("Error", "Could not load staff.",
                                 parent=self.ctx.parent)
            return
        mapping = {f"{r[3] or r[1]} ({r[1]})": r[0] for r in staff}
        if len(mapping) < 2:
            messagebox.showinfo("Need ≥2 staff",
                                "Not enough staff/instructor users.",
                                parent=self.ctx.parent)
            return
        src = _combo_dialog(self.ctx.parent, "Delegate from",
                            "From:", list(mapping.keys()))
        dst = _combo_dialog(self.ctx.parent, "Delegate to",
                            "To:", list(mapping.keys()))
        if not (src and dst):
            return
        if src == dst:
            messagebox.showerror("Same user",
                                 "Source and destination are the same.",
                                 parent=self.ctx.parent)
            return
        start = Prompt.iso_date(self.ctx.parent, "Start",
                                "Active from (YYYY-MM-DD):") \
            or date.today().isoformat()
        end = Prompt.iso_date(
            self.ctx.parent, "End", "Active to (YYYY-MM-DD):",
            initial=(date.today() + timedelta(days=14)).isoformat()
        ) or (date.today() + timedelta(days=14)).isoformat()
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_delegations
                   (from_user, to_user, active_from, active_to)
                   VALUES (?,?,?,?)""",
                (mapping[src], mapping[dst], start, end))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("delegation insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "delegate", "abs_tracker_delegations", "",
              f"{mapping[src]}→{mapping[dst]} {start}..{end}")
        messagebox.showinfo("Delegated",
                            f"{src} → {dst} from {start} to {end}",
                            parent=self.ctx.parent)

    # --- #12 ----------------------------------------------------------
    @safe("Request comments")
    def show_request_comment_thread(self) -> None:
        rid = simpledialog.askinteger("Comments", "Request id:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT created_at, author, body
                   FROM abs_tracker_request_comments
                   WHERE request_id=? ORDER BY created_at""",
                (rid,)).fetchall()
        except sqlite3.Error:
            logger.exception("comment fetch failed rid=%s", rid)
            messagebox.showerror("Error", "Could not load comments.",
                                 parent=self.ctx.parent)
            return
        win = tk.Toplevel(self.ctx.parent)
        win.title(f"Comments on request {rid}")
        win.geometry("620x460")
        txt = tk.Text(win, wrap="word")
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        for ts, author, body in rows:
            txt.insert("end", f"[{ts}] {author}:\n{body}\n\n")
        txt.config(state="disabled")
        entry = tk.Text(win, height=4)
        entry.pack(fill="x", padx=10)

        def post():
            body = entry.get("1.0", "end").strip()
            if not body:
                return
            try:
                self.ctx.db.cur.execute(
                    """INSERT INTO abs_tracker_request_comments
                       (request_id, author, body) VALUES (?,?,?)""",
                    (rid, self.ctx.username or "?", body))
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception("comment post failed rid=%s", rid)
                messagebox.showerror("Failed", str(e), parent=win)
                return
            audit(self.ctx, "request_comment", "absence_requests",
                  rid, body[:120])
            txt.config(state="normal")
            txt.insert("end",
                       f"[{datetime.now().isoformat(timespec='seconds')}] "
                       f"{self.ctx.username or '?'}:\n{body}\n\n")
            txt.config(state="disabled")
            entry.delete("1.0", "end")

        tk.Button(win, text="Post", command=post, bg="#2563eb", fg="white",
                  relief="flat", padx=12, pady=4).pack(pady=8)

    # --- #13 ----------------------------------------------------------
    @safe("Request templates")
    def manage_request_templates(self) -> None:
        win = tk.Toplevel(self.ctx.parent)
        win.title("Request templates")
        win.geometry("560x420")
        tree = ttk.Treeview(win, columns=("id", "name"), show="headings")
        for c, w in zip(("id", "name"), (60, 400)):
            tree.heading(c, text=c)
            tree.column(c, width=w)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        def refresh():
            try:
                tree.delete(*tree.get_children())
                for row in self.ctx.db.cur.execute(
                        "SELECT id, name FROM abs_tracker_request_templates "
                        "ORDER BY name"):
                    tree.insert("", "end", values=row)
            except sqlite3.Error:
                logger.exception("template refresh failed")

        def add():
            name = Prompt.non_empty(win, "Template name", "Name:", min_len=1)
            if not name:
                return
            body = simpledialog.askstring("Body", "Template body:",
                                          parent=win) or ""
            try:
                self.ctx.db.cur.execute(
                    """INSERT OR REPLACE INTO abs_tracker_request_templates
                       (name, body) VALUES (?,?)""", (name, body))
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception("template insert failed name=%s", name)
                messagebox.showerror("Failed", str(e), parent=win)
                return
            audit(self.ctx, "template_add",
                  "abs_tracker_request_templates", "", name)
            refresh()

        def delete():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Select", "Pick a template first.",
                                    parent=win)
                return
            tid = tree.item(sel[0])["values"][0]
            try:
                self.ctx.db.cur.execute(
                    "DELETE FROM abs_tracker_request_templates WHERE id=?",
                    (tid,))
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception("template delete failed tid=%s", tid)
                messagebox.showerror("Failed", str(e), parent=win)
                return
            audit(self.ctx, "template_delete",
                  "abs_tracker_request_templates", tid, "")
            refresh()

        bar = tk.Frame(win); bar.pack(fill="x", pady=5)
        tk.Button(bar, text="➕ Add", command=add, bg="#16a34a",
                  fg="white", relief="flat", padx=10
                  ).pack(side="left", padx=6)
        tk.Button(bar, text="🗑 Delete", command=delete, bg="#dc2626",
                  fg="white", relief="flat", padx=10
                  ).pack(side="left", padx=6)
        refresh()


# ===========================================================================
# PolicyService — features #14–#18
# ===========================================================================

class PolicyService:
    """Per-module / default policy, status vocab, auto-excuse, grace."""

    def __init__(self, ctx: AdminContext, module_picker: ModulePicker
                 ) -> None:
        self.ctx = ctx
        self.module_picker = module_picker

    # --- #14 ----------------------------------------------------------
    @safe("Module policy")
    def edit_module_policy(self) -> None:
        mc = self.module_picker.pick("Policy for which module?")
        if not mc:
            return
        try:
            row = self.ctx.db.cur.execute(
                """SELECT min_percent, late_as_absent, grace_minutes, notes
                   FROM abs_tracker_module_policy WHERE module_code=?""",
                (mc,)).fetchone()
        except sqlite3.Error:
            logger.exception("policy fetch failed mc=%s", mc)
            row = None
        cur_pct, cur_lta, cur_grace, cur_notes = row or (80.0, 0, 5, "")
        pct = simpledialog.askfloat(
            "Min %", f"Minimum attendance % (current {cur_pct})",
            parent=self.ctx.parent, minvalue=0, maxvalue=100)
        lta = simpledialog.askinteger(
            "Late=Absent",
            f"1 to count late as absent (current {cur_lta}):",
            parent=self.ctx.parent, minvalue=0, maxvalue=1)
        grace = simpledialog.askinteger(
            "Grace",
            f"Grace minutes before 'late' (current {cur_grace}):",
            parent=self.ctx.parent, minvalue=0, maxvalue=120)
        notes = simpledialog.askstring("Notes", "Notes:",
                                       parent=self.ctx.parent) or cur_notes
        try:
            self.ctx.db.cur.execute(
                """INSERT OR REPLACE INTO abs_tracker_module_policy
                   (module_code, min_percent, late_as_absent,
                    grace_minutes, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (mc, pct if pct is not None else cur_pct,
                 lta if lta is not None else cur_lta,
                 grace if grace is not None else cur_grace, notes))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("policy save failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "module_policy", "abs_tracker_module_policy", mc,
              f"pct={pct} lta={lta} grace={grace}")
        messagebox.showinfo("Saved", f"Policy for {mc} saved.",
                            parent=self.ctx.parent)

    # --- #15 ----------------------------------------------------------
    @safe("Default policy")
    def set_default_min_percent(self) -> None:
        current = _get_setting(self.ctx.db, "default_min_pct", "80")
        pct = simpledialog.askfloat(
            "Default min %",
            f"Default attendance min % (now {current}):",
            parent=self.ctx.parent, minvalue=0, maxvalue=100)
        if pct is None:
            return
        try:
            _set_setting(self.ctx.db, "default_min_pct", pct)
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "default_policy", "settings",
              "default_min_pct", str(pct))
        messagebox.showinfo("Saved", f"Default min % = {pct}",
                            parent=self.ctx.parent)

    # --- #16 ----------------------------------------------------------
    @safe("Status vocabulary")
    def manage_status_vocabulary(self) -> None:
        win = tk.Toplevel(self.ctx.parent)
        win.title("Status vocabulary")
        win.geometry("560x420")
        tree = ttk.Treeview(win, columns=("code", "label", "counts_as"),
                            show="headings")
        for c, w in zip(("code", "label", "counts_as"), (120, 200, 140)):
            tree.heading(c, text=c)
            tree.column(c, width=w)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        def refresh():
            try:
                tree.delete(*tree.get_children())
                for row in self.ctx.db.cur.execute(
                        """SELECT code, label, counts_as
                           FROM abs_tracker_statuses ORDER BY code"""):
                    tree.insert("", "end", values=row)
            except sqlite3.Error:
                logger.exception("status refresh failed")

        def add():
            code = Prompt.non_empty(win, "Code", "Status code:", min_len=1)
            if not code:
                return
            label = simpledialog.askstring("Label", "Display label:",
                                           parent=win) or code
            counts = _combo_dialog(
                win, "Counts as", "Counts as:",
                ["present", "absent", "late", "excused"]) or "absent"
            try:
                self.ctx.db.cur.execute(
                    """INSERT OR REPLACE INTO abs_tracker_statuses
                       (code, label, counts_as) VALUES (?,?,?)""",
                    (code, label, counts))
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception("status insert failed")
                messagebox.showerror("Failed", str(e), parent=win)
                return
            audit(self.ctx, "status_add", "abs_tracker_statuses",
                  code, label)
            refresh()

        tk.Button(win, text="➕ Add", command=add, bg="#16a34a",
                  fg="white", relief="flat").pack(pady=6)
        refresh()

    # --- #17 ----------------------------------------------------------
    @safe("Auto-excuse rules")
    def add_auto_excuse_rule(self) -> None:
        ev_type = Prompt.non_empty(
            self.ctx.parent, "Event type",
            "Academic-calendar event_type to auto-excuse "
            "(e.g. 'holiday','exam'):",
            min_len=2)
        if not ev_type:
            return
        try:
            self.ctx.db.cur.execute(
                "INSERT INTO abs_tracker_auto_excuse_rules (event_type) "
                "VALUES (?)", (ev_type,))
            events = self.ctx.db.cur.execute(
                """SELECT date FROM academic_calendar_events
                   WHERE event_type=?""", (ev_type,)).fetchall()
            updated = 0
            for (d,) in events:
                cur = self.ctx.db.cur.execute(
                    """UPDATE attendance
                       SET status='excused',
                           reason='auto: '||?
                       WHERE date=? AND status='absent'""",
                    (ev_type, d))
                updated += cur.rowcount
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("auto-excuse failed ev=%s", ev_type)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "auto_excuse", "attendance", ev_type,
              f"updated={updated}")
        messagebox.showinfo(
            "Applied",
            f"Auto-excused {updated} absence(s) for '{ev_type}'.",
            parent=self.ctx.parent)

    # --- #18 ----------------------------------------------------------
    @safe("Grace period")
    def set_global_grace_minutes(self) -> None:
        current = _get_setting(self.ctx.db, "global_grace", "0")
        mins = simpledialog.askinteger(
            "Grace minutes",
            f"Global grace (current {current}):",
            parent=self.ctx.parent, minvalue=0, maxvalue=120)
        if mins is None:
            return
        try:
            _set_setting(self.ctx.db, "global_grace", mins)
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "grace_period", "settings",
              "global_grace", str(mins))
        messagebox.showinfo("Saved", f"Global grace = {mins} min",
                            parent=self.ctx.parent)


# ===========================================================================
# ReportingService — features #19–#26
# ===========================================================================

class ReportingService:
    """At-risk, module health, cohorts, trends, scheduled reports, heatmap."""

    def __init__(self, ctx: AdminContext) -> None:
        self.ctx = ctx

    # --- #19 ----------------------------------------------------------
    @safe("At-risk students")
    def show_at_risk_students(self) -> None:
        threshold = simpledialog.askfloat(
            "Threshold", "Below what % counts as at-risk?",
            parent=self.ctx.parent, minvalue=0, maxvalue=100,
            initialvalue=80) or 80
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id,
                          COALESCE(s.first_name||' '||s.last_name,
                                   a.student_id) AS name,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(*),0) * 100 AS pct,
                          COUNT(*) AS total
                   FROM attendance a
                   LEFT JOIN students s ON s.student_id = a.student_id
                   GROUP BY a.student_id
                   HAVING pct IS NOT NULL AND pct < ?
                   ORDER BY pct ASC""", (threshold,)).fetchall()
        except sqlite3.Error:
            logger.exception("at-risk query failed")
            messagebox.showerror("Error", "Could not run report.",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "at_risk_report", "attendance", "",
              f"threshold={threshold} n={len(rows)}")
        _report_window(self.ctx.parent, f"At-risk (<{threshold:.0f}%)",
                       ("student_id", "name", "pct", "sessions"), rows,
                       db=self.ctx.db, user=self.ctx.user,
                       widths=[110, 260, 90, 90])

    # --- #20 ----------------------------------------------------------
    @safe("Module health")
    def show_module_health(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT a.module_code,
                          COALESCE(m.module_name, a.module_code) AS name,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(*),0) * 100,
                          COUNT(*) AS total
                   FROM attendance a
                   LEFT JOIN modules m ON m.module_code = a.module_code
                   GROUP BY a.module_code ORDER BY 3 ASC""").fetchall()
        except sqlite3.Error:
            logger.exception("module health query failed")
            rows = []
        _report_window(self.ctx.parent, "Module health",
                       ("module", "name", "avg %", "rows"), rows,
                       db=self.ctx.db, user=self.ctx.user,
                       widths=[110, 360, 90, 90])

    # --- #21 ----------------------------------------------------------
    @safe("Cohort compare")
    def compare_cohorts(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT COALESCE(s.course,'(none)') AS cohort,
                          COUNT(DISTINCT s.student_id) AS students,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(a.id),0) * 100 AS avg_pct
                   FROM students s
                   LEFT JOIN attendance a ON a.student_id = s.student_id
                   GROUP BY cohort ORDER BY 3 DESC""").fetchall()
        except sqlite3.Error:
            logger.exception("cohort compare failed")
            rows = []
        _report_window(self.ctx.parent, "Cohort comparison",
                       ("cohort", "students", "avg %"), rows,
                       db=self.ctx.db, user=self.ctx.user,
                       widths=[320, 110, 110])

    # --- #22 ----------------------------------------------------------
    @safe("Trend chart")
    def show_weekly_trend(self) -> None:
        try:
            weeks = self.ctx.db.cur.execute(
                """SELECT strftime('%Y-%W', date) AS wk,
                          a.module_code,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(*),0) * 100
                   FROM attendance a
                   GROUP BY wk, a.module_code ORDER BY wk""").fetchall()
        except sqlite3.Error:
            logger.exception("trend query failed")
            weeks = []
        _report_window(self.ctx.parent, "Weekly % per module",
                       ("week", "module", "pct"), weeks,
                       db=self.ctx.db, user=self.ctx.user,
                       widths=[110, 140, 120])

    # --- #23 ----------------------------------------------------------
    @safe("Term compare")
    def compare_terms(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT s.name AS semester, s.start_date, s.end_date,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(a.id),0) * 100 AS pct,
                          COUNT(a.id) AS rows
                   FROM semesters s
                   LEFT JOIN attendance a
                       ON a.date BETWEEN s.start_date AND s.end_date
                   GROUP BY s.id ORDER BY s.start_date""").fetchall()
        except sqlite3.Error:
            logger.exception("term compare failed")
            rows = []
        _report_window(self.ctx.parent, "Term-over-term",
                       ("semester", "start", "end", "pct", "rows"), rows,
                       db=self.ctx.db, user=self.ctx.user)

    # --- #24 ----------------------------------------------------------
    @safe("Schedule report")
    def schedule_recurring_report(self) -> None:
        name = Prompt.non_empty(self.ctx.parent, "Name",
                                "Report name:", min_len=2)
        if not name:
            return
        freq = _combo_dialog(self.ctx.parent, "Frequency", "Frequency:",
                             ["daily", "weekly", "monthly"]) or "weekly"
        recips = simpledialog.askstring(
            "Recipients", "Comma-separated emails:",
            parent=self.ctx.parent) or ""
        rtype = _combo_dialog(
            self.ctx.parent, "Type", "Report type:",
            ["at_risk", "module_health", "cohort_compare"]) or "at_risk"
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_scheduled_reports
                   (name, frequency, recipients, report_type)
                   VALUES (?,?,?,?)""",
                (name, freq, recips, rtype))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("scheduled report insert failed name=%s", name)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "schedule_report",
              "abs_tracker_scheduled_reports", "",
              f"{name} {freq} {rtype}")
        messagebox.showinfo(
            "Scheduled",
            f"{name} ({freq}) → {recips or '(none)'}",
            parent=self.ctx.parent)

    # --- #25 ----------------------------------------------------------
    @safe("Consecutive absences")
    def show_top_absentees(self) -> None:
        n = simpledialog.askinteger("Top N", "How many to show?",
                                    parent=self.ctx.parent,
                                    minvalue=1, initialvalue=20) or 20
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT student_id, COUNT(*) AS absences
                   FROM attendance WHERE status='absent'
                   GROUP BY student_id
                   ORDER BY absences DESC LIMIT ?""", (n,)).fetchall()
        except sqlite3.Error:
            logger.exception("absentee query failed")
            rows = []
        _report_window(self.ctx.parent, f"Top {n} by absence count",
                       ("student", "absences"), rows,
                       db=self.ctx.db, user=self.ctx.user,
                       widths=[180, 120])

    # --- #26 ----------------------------------------------------------
    @safe("Heatmap")
    def show_dayofweek_heatmap(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT CASE strftime('%w', date)
                            WHEN '0' THEN 'Sun' WHEN '1' THEN 'Mon'
                            WHEN '2' THEN 'Tue' WHEN '3' THEN 'Wed'
                            WHEN '4' THEN 'Thu' WHEN '5' THEN 'Fri'
                            WHEN '6' THEN 'Sat' END AS dow,
                          COUNT(*) AS absences
                   FROM attendance WHERE status='absent'
                   GROUP BY dow ORDER BY dow""").fetchall()
        except sqlite3.Error:
            logger.exception("heatmap query failed")
            rows = []
        _report_window(self.ctx.parent, "Absences by day-of-week",
                       ("day", "absences"), rows,
                       db=self.ctx.db, user=self.ctx.user,
                       widths=[140, 140])


# ===========================================================================
# NotificationService — features #27–#30
# ===========================================================================

def _parents_of(db, sid: str) -> list[str]:
    """Return parent_ids linked to a student. Empty list on error."""
    try:
        return [str(r[0]) for r in db.cur.execute(
            "SELECT parent_id FROM parent_student_links WHERE student_id=?",
            (sid,)).fetchall()]
    except sqlite3.Error:
        logger.exception("parents lookup failed sid=%s", sid)
        return []


class NotificationService:
    """Threshold alerts, parent notifications, bulk announcements, SMS."""

    def __init__(self, ctx: AdminContext, student_picker: StudentPicker,
                 module_picker: ModulePicker) -> None:
        self.ctx = ctx
        self.student_picker = student_picker
        self.module_picker = module_picker

    # --- #27 ----------------------------------------------------------
    @safe("Threshold alerts")
    def create_threshold_alerts(self) -> None:
        threshold = simpledialog.askfloat(
            "Threshold", "Alert below %:",
            parent=self.ctx.parent, initialvalue=75) or 75
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(*),0) * 100 AS pct
                   FROM attendance a GROUP BY a.student_id
                   HAVING pct IS NOT NULL AND pct < ?""",
                (threshold,)).fetchall()
        except sqlite3.Error:
            logger.exception("threshold scan failed")
            messagebox.showerror("Error", "Could not scan attendance.",
                                 parent=self.ctx.parent)
            return
        created = 0
        try:
            for sid, pct in rows:
                # FIX: original used parent_id='' which orphaned every alert.
                # Insert one row per real linked parent; if none exist, leave
                # the alert with parent_id='' so an admin can still see it.
                parents = _parents_of(self.ctx.db, sid) or [""]
                for pid in parents:
                    self.ctx.db.cur.execute(
                        """INSERT INTO parent_notifications
                           (parent_id, student_id, notification_type,
                            notification_content, created_date, read_status)
                           VALUES (?, ?, 'attendance_alert', ?, ?, 0)""",
                        (pid, sid,
                         f"Attendance at {pct:.1f}% (below {threshold:.0f}%)",
                         datetime.now().isoformat(timespec="seconds")))
                    created += 1
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("threshold alert insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "threshold_alerts", "parent_notifications", "",
              f"threshold={threshold} created={created}")
        messagebox.showinfo("Alerts",
                            f"Created {created} alert row(s).",
                            parent=self.ctx.parent)

    # --- #28 ----------------------------------------------------------
    @safe("Parent notifications")
    def notify_parents_for_student(self) -> None:
        sid = self.student_picker.pick("Notify parents of which student?")
        if not sid:
            return
        parents = _parents_of(self.ctx.db, sid)
        if not parents:
            messagebox.showinfo(
                "No parents",
                "No parents linked to this student.",
                parent=self.ctx.parent)
            return
        try:
            recent = self.ctx.db.cur.execute(
                """SELECT date, status FROM attendance
                   WHERE student_id=? ORDER BY date DESC LIMIT 10""",
                (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("recent attendance fetch failed sid=%s", sid)
            recent = []
        content = "Recent attendance: " + "; ".join(
            f"{d}={s}" for d, s in recent)
        try:
            for pid in parents:
                self.ctx.db.cur.execute(
                    """INSERT INTO parent_notifications
                       (parent_id, student_id, notification_type,
                        notification_content, created_date, read_status)
                       VALUES (?, ?, 'attendance_update', ?, ?, 0)""",
                    (pid, sid, content,
                     datetime.now().isoformat(timespec="seconds")))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("parent notify failed sid=%s", sid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "parent_notify", "parent_notifications", sid,
              f"parents={len(parents)}")
        messagebox.showinfo("Sent", f"Notified {len(parents)} parent(s).",
                            parent=self.ctx.parent)

    # --- #29 ----------------------------------------------------------
    @safe("Bulk announcement")
    def post_bulk_announcement(self) -> None:
        mc = self.module_picker.pick("Announce to which module?")
        if not mc:
            return
        msg = Prompt.non_empty(self.ctx.parent, "Message",
                               "Announcement text:", min_len=2)
        if not msg:
            return
        try:
            roster = self.ctx.db.get_course_students(mc)
        except Exception:
            logger.exception("roster fetch failed mc=%s", mc)
            messagebox.showerror("Error", "Could not load roster.",
                                 parent=self.ctx.parent)
            return
        if not roster:
            messagebox.showinfo("Empty", "No students enrolled.",
                                parent=self.ctx.parent)
            return
        n_rows = 0
        try:
            for sid, *_ in roster:
                # FIX: original wrote parent_id='' so nothing was actually
                # routed. Resolve parents per student; fall back to '' so the
                # row still exists for the admin view.
                parents = _parents_of(self.ctx.db, sid) or [""]
                for pid in parents:
                    self.ctx.db.cur.execute(
                        """INSERT INTO parent_notifications
                           (parent_id, student_id, notification_type,
                            notification_content, created_date, read_status)
                           VALUES (?, ?, 'announcement', ?, ?, 0)""",
                        (pid, sid, msg,
                         datetime.now().isoformat(timespec="seconds")))
                    n_rows += 1
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("bulk announcement failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "bulk_announcement",
              "parent_notifications", mc,
              f"students={len(roster)} rows={n_rows} msg={msg[:80]}")
        messagebox.showinfo("Sent",
                            f"Announcement posted for {len(roster)} "
                            f"student(s) ({n_rows} notification rows).",
                            parent=self.ctx.parent)

    # --- #30 ----------------------------------------------------------
    @safe("SMS fallback")
    def queue_sms_fallback(self) -> None:
        threshold = simpledialog.askfloat(
            "Threshold", "Below %:",
            parent=self.ctx.parent, initialvalue=70) or 70
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS sms_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT, body TEXT,
                    queued_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'queued')""")
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(*),0) * 100 AS pct
                   FROM attendance a GROUP BY a.student_id
                   HAVING pct IS NOT NULL AND pct < ?""",
                (threshold,)).fetchall()
            queued = 0
            for sid, pct in rows:
                self.ctx.db.cur.execute(
                    "INSERT INTO sms_messages (recipient, body) VALUES (?,?)",
                    (sid, f"ALERT: attendance {pct:.1f}% "
                          f"below {threshold:.0f}%"))
                queued += 1
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("SMS queue failed threshold=%s", threshold)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "sms_queue", "sms_messages", "", f"n={queued}")
        messagebox.showinfo("Queued",
                            f"{queued} SMS message(s) queued.",
                            parent=self.ctx.parent)


# ===========================================================================
# IntegrationService — features #31–#37
# ===========================================================================

class IntegrationService:
    """Calendar, schedule, risk feed, grade/wellbeing/discipline/finance."""

    def __init__(self, ctx: AdminContext, student_picker: StudentPicker,
                 module_picker: ModulePicker) -> None:
        self.ctx = ctx
        self.student_picker = student_picker
        self.module_picker = module_picker

    # --- #31 ----------------------------------------------------------
    @safe("Calendar link")
    def show_upcoming_calendar_events(self) -> None:
        n = simpledialog.askinteger(
            "Window", "Look ahead how many days?",
            parent=self.ctx.parent, initialvalue=30) or 30
        today = date.today().isoformat()
        end = (date.today() + timedelta(days=n)).isoformat()
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT date, name, event_type
                   FROM academic_calendar_events
                   WHERE date BETWEEN ? AND ?
                   ORDER BY date""", (today, end)).fetchall()
        except sqlite3.Error:
            logger.exception("calendar fetch failed")
            rows = []
        _show_table(self.ctx.parent, f"Calendar ({today} → {end})",
                    ("date", "name", "type"), rows, widths=[120, 480, 140])

    # --- #32 ----------------------------------------------------------
    @safe("Pre-generate sessions")
    def show_module_schedule(self) -> None:
        mc = self.module_picker.pick("Sessions for which module?")
        if not mc:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT day_of_week, start_time, end_time, room_id,
                          instructor_id, semester, year, status
                   FROM module_schedule WHERE module_code=?
                   ORDER BY day_of_week, start_time""", (mc,)).fetchall()
        except sqlite3.Error:
            logger.exception("schedule fetch failed mc=%s", mc)
            rows = []
        _show_table(self.ctx.parent, f"Scheduled sessions for {mc}",
                    ("day", "start", "end", "room", "instructor",
                     "sem", "yr", "status"), rows)

    # --- #33 ----------------------------------------------------------
    @safe("Risk feed")
    def feed_student_risk_assessment(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT student_id,
                          SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(*),0) * 100 AS pct,
                          COUNT(*)
                   FROM attendance GROUP BY student_id""").fetchall()
        except sqlite3.Error:
            logger.exception("risk feed read failed")
            messagebox.showerror("Error", "Could not read attendance.",
                                 parent=self.ctx.parent)
            return
        created = 0
        today = date.today().isoformat()
        try:
            for sid, pct, _tot in rows:
                pct = pct or 0
                level = ("low" if pct >= 85
                         else "medium" if pct >= 70
                         else "high")
                score = round(100 - pct, 2)
                self.ctx.db.cur.execute(
                    """INSERT INTO student_risk_assessment
                       (student_id, risk_score, risk_level,
                        assessment_date, prediction_model, confidence)
                       VALUES (?,?,?,?,?,?)""",
                    (sid, score, level, today, "attendance_basic", 0.9))
                created += 1
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("risk feed insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "risk_feed", "student_risk_assessment", "",
              f"rows={created}")
        messagebox.showinfo("Done", f"Wrote {created} risk rows.",
                            parent=self.ctx.parent)

    # --- #34 ----------------------------------------------------------
    @safe("Grade link")
    def show_grade_penalty_candidates(self) -> None:
        threshold = simpledialog.askfloat(
            "Threshold", "Penalty below %:",
            parent=self.ctx.parent, initialvalue=50) or 50
        try:
            # FIX: original used `HAVING 3 < ?` — a literal-only compare.
            # Now genuinely filters on the aggregated attendance percentage.
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id, a.module_code,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(*),0) * 100 AS pct
                   FROM attendance a
                   GROUP BY a.student_id, a.module_code
                   HAVING pct IS NOT NULL AND pct < ?""",
                (threshold,)).fetchall()
        except sqlite3.Error:
            logger.exception("grade link failed")
            rows = []
        _show_table(self.ctx.parent,
                    f"Attendance penalty candidates (<{threshold:.0f}%)",
                    ("student", "module", "pct"),
                    [(s, m, f"{p:.1f}") for s, m, p in rows])
        audit(self.ctx, "grade_link", "attendance", "",
              f"threshold={threshold} n={len(rows)}")

    # --- #35 ----------------------------------------------------------
    @safe("Wellbeing link")
    def show_absences_vs_mood(self) -> None:
        try:
            # Match the canonical schema in
            # infrastructure/database/schemas/health_wellness_schemas.py
            # (column is `mood_rating`, not `mood`).
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS mental_health_checkins (
                    checkin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    mood_rating INTEGER NOT NULL,
                    stress_level INTEGER NOT NULL,
                    sleep_quality INTEGER,
                    notes TEXT,
                    checkin_date TEXT DEFAULT CURRENT_DATE,
                    checkin_time TEXT DEFAULT CURRENT_TIME,
                    follow_up_required BOOLEAN DEFAULT 0)""")
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id,
                          SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END)
                              AS abs_cnt,
                          (SELECT AVG(mood_rating) FROM mental_health_checkins mc
                           WHERE mc.student_id=a.student_id) AS avg_mood
                   FROM attendance a GROUP BY a.student_id
                   ORDER BY abs_cnt DESC LIMIT 50""").fetchall()
        except sqlite3.Error:
            logger.exception("wellbeing link query failed")
            rows = []

        def _open_wellbeing_gui():
            try:
                import tkinter as tk
                from education_system.university_system.modules.domain.student_affairs.student_wellbeing.gui.wellbeing_gui import (  # noqa: E501
                    WellbeingFrame,
                )
                win = tk.Toplevel(self.ctx.parent)
                win.title("Wellbeing")
                win.geometry("1000x650")
                WellbeingFrame(win, db_path=self.ctx.db.path,
                               auth=getattr(self.ctx, "auth", None)
                               ).pack(fill="both", expand=True)
            except Exception:
                logger.exception("could not open Wellbeing GUI")
                from tkinter import messagebox
                messagebox.showerror(
                    "Wellbeing", "Could not open the Wellbeing GUI "
                    "(see log).", parent=self.ctx.parent)

        _show_table(self.ctx.parent, "Absences vs mood",
                    ("student", "absences", "avg_mood"), rows,
                    extra_button=("📊  Open Wellbeing GUI",
                                  _open_wellbeing_gui))

    # --- #36 ----------------------------------------------------------
    @safe("Disciplinary action")
    def raise_disciplinary_action(self) -> None:
        sid = self.student_picker.pick("Disciplinary action for?")
        if not sid:
            return
        reason = simpledialog.askstring(
            "Reason", "Reason:",
            parent=self.ctx.parent) or "Repeated unjustified absences"
        if not Prompt.confirm(self.ctx.parent, "Confirm",
                              f"Raise written warning for {sid}?"):
            return
        try:
            today = date.today().isoformat()
            now = datetime.now().isoformat(timespec="seconds")
            # disciplinary_actions.record_id is a FK to
            # disciplinary_records(record_id); we must create the parent
            # row first or the FK constraint fails.
            self.ctx.db.cur.execute(
                """INSERT INTO disciplinary_records
                   (user_id, offense_type, description, date_occurred,
                    date_reported, reported_by, severity, status)
                   VALUES (?, 'attendance', ?, ?, ?, ?, 'minor', 'under_review')""",
                (sid, reason, today, today, self.ctx.username))
            record_id = self.ctx.db.cur.lastrowid
            self.ctx.db.cur.execute(
                """INSERT INTO disciplinary_actions
                   (record_id, action_type, action_level, effective_date,
                    duration_days, imposed_by, reason, created_at)
                   VALUES (?, 'warning', 'written', ?, 0, ?, ?, ?)""",
                (record_id, today, self.ctx.username, reason, now))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("disciplinary insert failed sid=%s", sid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "disciplinary", "disciplinary_actions", sid, reason)
        messagebox.showinfo("Recorded",
                            f"Disciplinary action logged for {sid}.",
                            parent=self.ctx.parent)

    # --- #37 ----------------------------------------------------------
    @safe("Finance link")
    def show_scholarship_attendance_check(self) -> None:
        threshold = simpledialog.askfloat(
            "Threshold", "Below %:",
            parent=self.ctx.parent, initialvalue=80) or 80
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS student_scholarships (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT, scholarship_id INTEGER, status TEXT)""")
            # FIX: original used `HAVING 2 < ?` — same literal-compare bug.
            rows = self.ctx.db.cur.execute(
                """SELECT ss.student_id,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(a.id),0) * 100 AS pct
                   FROM student_scholarships ss
                   LEFT JOIN attendance a ON a.student_id = ss.student_id
                   GROUP BY ss.student_id
                   HAVING pct IS NOT NULL AND pct < ?""",
                (threshold,)).fetchall()
        except sqlite3.Error:
            logger.exception("scholarship check failed")
            rows = []
        _show_table(self.ctx.parent, "Scholarship attendance check",
                    ("student", "pct"),
                    [(s, f"{p:.1f}") for s, p in rows])


# ===========================================================================
# BulkOperationsService — features #38–#41
# ===========================================================================

class BulkOperationsService:
    """Whole-class roll, copy previous day, recurring absence, reassign."""

    def __init__(self, ctx: AdminContext, student_picker: StudentPicker,
                 module_picker: ModulePicker) -> None:
        self.ctx = ctx
        self.student_picker = student_picker
        self.module_picker = module_picker

    # --- #38 ----------------------------------------------------------
    @safe("Bulk present")
    def mark_module_all_present(self) -> None:
        mc = self.module_picker.pick("Module:")
        if not mc:
            return
        d = Prompt.iso_date(self.ctx.parent)
        if not d:
            return
        try:
            roster = self.ctx.db.get_course_students(mc)
        except Exception:
            logger.exception("roster fetch failed mc=%s", mc)
            messagebox.showerror("Error", "Could not load roster.",
                                 parent=self.ctx.parent)
            return
        if not roster:
            messagebox.showinfo("Empty", "No students enrolled.",
                                parent=self.ctx.parent)
            return
        if not Prompt.confirm(self.ctx.parent, "Confirm",
                              f"Mark {len(roster)} student(s) present on {d}?"):
            return
        try:
            for sid, *_ in roster:
                self.ctx.db.record_absence(sid, mc, d, "present",
                                           "bulk-present")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("bulk present failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "bulk_present", "attendance", mc,
              f"date={d} n={len(roster)}")
        messagebox.showinfo("Saved",
                            f"Marked {len(roster)} present on {d}.",
                            parent=self.ctx.parent)

    # --- #39 ----------------------------------------------------------
    @safe("Copy previous day")
    def copy_previous_day_roll(self) -> None:
        mc = self.module_picker.pick("Module:")
        if not mc:
            return
        d = Prompt.iso_date(self.ctx.parent, "Copy to date",
                            "Target date (YYYY-MM-DD):")
        if not d:
            return
        try:
            last = self.ctx.db.cur.execute(
                """SELECT MAX(date) FROM attendance
                   WHERE module_code=? AND date<?""",
                (mc, d)).fetchone()[0]
        except sqlite3.Error:
            logger.exception("previous-day lookup failed mc=%s", mc)
            messagebox.showerror("Error", "Could not look up previous roll.",
                                 parent=self.ctx.parent)
            return
        if not last:
            messagebox.showinfo("Nothing to copy",
                                "No prior attendance rows.",
                                parent=self.ctx.parent)
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT student_id, status, reason FROM attendance
                   WHERE module_code=? AND date=?""",
                (mc, last)).fetchall()
            for sid, status, reason in rows:
                self.ctx.db.record_absence(sid, mc, d, status, reason or "")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("copy previous day failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "copy_prev_day", "attendance", mc,
              f"from={last} to={d} n={len(rows)}")
        messagebox.showinfo("Copied",
                            f"Copied {len(rows)} row(s) {last} → {d}.",
                            parent=self.ctx.parent)

    # --- #40 ----------------------------------------------------------
    @safe("Recurring absence")
    def create_recurring_absence(self) -> None:
        sid = self.student_picker.pick("Student:")
        if not sid:
            return
        mc = self.module_picker.pick("Module:")
        if not mc:
            return
        start = Prompt.iso_date(self.ctx.parent, "First date",
                                "First date (YYYY-MM-DD):")
        if not start:
            return
        weeks = simpledialog.askinteger(
            "Weeks", "How many weeks?",
            parent=self.ctx.parent, minvalue=1, maxvalue=52)
        if not weeks:
            return
        status = _combo_dialog(
            self.ctx.parent, "Status", "Status:",
            ["absent", "excused", "late", "present"]) or "absent"
        d0 = datetime.strptime(start, "%Y-%m-%d").date()
        try:
            for w in range(weeks):
                d = (d0 + timedelta(days=7 * w)).isoformat()
                self.ctx.db.record_absence(sid, mc, d, status, "recurring")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("recurring absence failed sid=%s mc=%s",
                             sid, mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "recurring_absence", "attendance", sid,
              f"{mc} {start} x{weeks} {status}")
        messagebox.showinfo("Saved",
                            f"Created {weeks} rows for {sid}.",
                            parent=self.ctx.parent)

    # --- #41 ----------------------------------------------------------
    @safe("Reassign records")
    def reassign_records_on_transfer(self) -> None:
        sid = self.student_picker.pick("Student:")
        if not sid:
            return
        src = self.module_picker.pick("Source module:")
        if not src:
            return
        dst = self.module_picker.pick("Destination module:")
        if not dst:
            return
        if src == dst:
            messagebox.showerror("Same module",
                                 "Source and destination are identical.",
                                 parent=self.ctx.parent)
            return
        try:
            cur = self.ctx.db.cur.execute(
                """UPDATE attendance SET module_code=?
                   WHERE student_id=? AND module_code=?""",
                (dst, sid, src))
            n = cur.rowcount
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("reassign failed sid=%s %s→%s", sid, src, dst)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "reassign", "attendance", sid,
              f"{src}→{dst} n={n}")
        messagebox.showinfo("Reassigned",
                            f"Moved {n} row(s) {src} → {dst}.",
                            parent=self.ctx.parent)


# ===========================================================================
# SecurityAuditService — features #42–#46
# ===========================================================================

class SecurityAuditService:
    """Permission matrix, audit trail, impersonation, retention, GDPR."""

    def __init__(self, ctx: AdminContext, student_picker: StudentPicker
                 ) -> None:
        self.ctx = ctx
        self.student_picker = student_picker

    # --- #42 ----------------------------------------------------------
    @safe("Permission matrix")
    def show_permission_matrix(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT u.username, u.role, im.module_code
                   FROM users u
                   LEFT JOIN instructor_modules im
                       ON im.instructor_id = u.id
                   WHERE u.role IN ('admin','staff','instructor')
                   ORDER BY u.username""").fetchall()
        except sqlite3.Error:
            logger.exception("permission matrix failed")
            rows = []
        _show_table(self.ctx.parent, "Permission matrix",
                    ("user", "role", "module"), rows)

    # --- #43 ----------------------------------------------------------
    @safe("Full audit trail")
    def show_full_audit_trail(self) -> None:
        user = simpledialog.askstring(
            "Filter", "Filter by username (blank = all):",
            parent=self.ctx.parent) or ""
        q = ("SELECT ts, username, action, target, target_id, details "
             "FROM abs_tracker_audit")
        p: list = []
        if user:
            q += " WHERE username LIKE ?"
            p.append(f"%{user}%")
        q += " ORDER BY ts DESC LIMIT 1000"
        try:
            rows = self.ctx.db.cur.execute(q, p).fetchall()
        except sqlite3.Error:
            logger.exception("audit trail fetch failed")
            rows = []
        _show_table(self.ctx.parent, "Full audit trail",
                    ("ts", "user", "action", "target", "id", "details"),
                    rows, widths=[150, 120, 140, 100, 100, 350])

    # --- #44 ----------------------------------------------------------
    @safe("Impersonate")
    def impersonate_user_readonly(self) -> None:
        username = Prompt.non_empty(
            self.ctx.parent, "Impersonate",
            "Username to view as:", min_len=1)
        if not username:
            return
        try:
            other = self.ctx.db.lookup_user_by_username(username)
        except Exception:
            logger.exception("user lookup failed username=%s", username)
            other = None
        if not other:
            messagebox.showerror("Not found",
                                 f"No user '{username}'",
                                 parent=self.ctx.parent)
            return
        try:
            from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking import (  # noqa: E501
                absence_tracker as at,
            )
            new_root = tk.Toplevel(self.ctx.parent)
            at.launch_dashboard(new_root, self.ctx.db, other)
        except Exception as e:
            logger.exception("impersonate launch failed")
            messagebox.showerror("Failed",
                                 f"Could not launch impersonated session:\n{e}",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "impersonate", "users", other["id"], username)

    # --- #45 ----------------------------------------------------------
    @safe("Retention purge")
    def purge_per_retention_policy(self) -> None:
        years = simpledialog.askinteger(
            "Retention", "Purge attendance older than (years)?",
            parent=self.ctx.parent, minvalue=1, maxvalue=30)
        if not years:
            return
        cutoff = (date.today() - timedelta(days=365 * years)).isoformat()
        if not Prompt.confirm(
                self.ctx.parent, "Confirm purge",
                f"Permanently delete attendance rows before {cutoff}?\n"
                "This cannot be undone."):
            return
        try:
            cur = self.ctx.db.cur.execute(
                "DELETE FROM attendance WHERE date < ?", (cutoff,))
            removed = cur.rowcount
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_retention
                   (policy, years, applied_at) VALUES (?,?,?)""",
                (f"attendance<{cutoff}", years,
                 datetime.now().isoformat(timespec="seconds")))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("retention purge failed years=%s", years)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "retention_purge", "attendance", "",
              f"years={years} removed={removed}")
        messagebox.showinfo("Purged",
                            f"Removed {removed} row(s) before {cutoff}.",
                            parent=self.ctx.parent)

    # --- #46 ----------------------------------------------------------
    @safe("GDPR export")
    def gdpr_subject_export(self) -> None:
        sid = self.student_picker.pick("Export data for which student?")
        if not sid:
            return
        try:
            att = self.ctx.db.cur.execute(
                "SELECT * FROM attendance WHERE student_id=?",
                (sid,)).fetchall()
            req = self.ctx.db.cur.execute(
                "SELECT * FROM absence_requests WHERE student_id=?",
                (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("GDPR fetch failed sid=%s", sid)
            messagebox.showerror("Error", "Could not load student data.",
                                 parent=self.ctx.parent)
            return
        path = filedialog.asksaveasfilename(
            parent=self.ctx.parent, defaultextension=".json",
            initialfile=f"gdpr_{sid}.json")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "student_id": sid,
                    "attendance": [list(r) for r in att],
                    "absence_requests": [list(r) for r in req],
                }, fh, indent=2, default=str)
        except OSError as e:
            logger.exception("GDPR write failed path=%s", path)
            messagebox.showerror("Save failed", str(e),
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "gdpr_export", "students", sid, path)
        messagebox.showinfo("Exported", f"Data written:\n{path}",
                            parent=self.ctx.parent)


# ===========================================================================
# DiagnosticsService — features #47–#50
# ===========================================================================

class DiagnosticsService:
    """Orphan rows, missing sessions, enrolment mismatch, DB health."""

    def __init__(self, ctx: AdminContext) -> None:
        self.ctx = ctx

    # --- #47 ----------------------------------------------------------
    @safe("Orphan rows")
    def show_orphan_attendance_rows(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT a.id, a.student_id, a.module_code, a.date,
                          CASE WHEN s.student_id IS NULL THEN 'missing student'
                               ELSE '' END,
                          CASE WHEN m.module_code IS NULL THEN 'missing module'
                               ELSE '' END
                   FROM attendance a
                   LEFT JOIN students s ON s.student_id = a.student_id
                   LEFT JOIN modules m  ON m.module_code = a.module_code
                   WHERE s.student_id IS NULL OR m.module_code IS NULL
                   ORDER BY a.date DESC""").fetchall()
        except sqlite3.Error:
            logger.exception("orphan scan failed")
            rows = []
        _show_table(self.ctx.parent, f"Orphan rows ({len(rows)})",
                    ("id", "student_id", "module_code", "date",
                     "student?", "module?"), rows)
        audit(self.ctx, "orphan_scan", "attendance", "", f"n={len(rows)}")

    # --- #48 ----------------------------------------------------------
    @safe("Missing sessions")
    def show_modules_without_attendance(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT ms.module_code, ms.day_of_week, ms.start_time,
                          ms.semester
                   FROM module_schedule ms
                   LEFT JOIN attendance a ON a.module_code = ms.module_code
                   WHERE a.id IS NULL
                   ORDER BY ms.module_code""").fetchall()
        except sqlite3.Error:
            logger.exception("missing sessions query failed")
            rows = []
        _show_table(
            self.ctx.parent,
            f"Modules with scheduled sessions but no attendance ({len(rows)})",
            ("module", "day", "start", "semester"), rows)

    # --- #49 ----------------------------------------------------------
    @safe("Enrollment mismatch")
    def show_enrollment_mismatches(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT a.id, a.student_id, a.module_code, a.date
                   FROM attendance a
                   LEFT JOIN student_modules sm
                     ON sm.student_id = a.student_id
                    AND sm.module_code = a.module_code
                   WHERE sm.id IS NULL
                   ORDER BY a.date DESC""").fetchall()
        except sqlite3.Error:
            logger.exception("enrolment mismatch query failed")
            rows = []
        _show_table(self.ctx.parent,
                    f"Enrollment mismatches ({len(rows)})",
                    ("id", "student", "module", "date"), rows)
        audit(self.ctx, "enrollment_mismatch", "attendance", "",
              f"n={len(rows)}")

    # --- #50 ----------------------------------------------------------
    @safe("DB health")
    def show_database_health(self) -> None:
        stats: list[tuple] = []
        for t in ("attendance", "absence_requests", "students", "modules",
                  "student_modules", "instructor_modules", "users",
                  "abs_tracker_audit", "abs_tracker_trash"):
            try:
                n = self.ctx.db.cur.execute(
                    f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                stats.append((t, n, "ok"))
            except sqlite3.Error as e:
                logger.exception("count failed table=%s", t)
                stats.append((t, "?", str(e)))
        try:
            integrity = self.ctx.db.cur.execute(
                "PRAGMA integrity_check").fetchone()[0]
            journal = self.ctx.db.cur.execute(
                "PRAGMA journal_mode").fetchone()[0]
            page_size = self.ctx.db.cur.execute(
                "PRAGMA page_size").fetchone()[0]
            page_count = self.ctx.db.cur.execute(
                "PRAGMA page_count").fetchone()[0]
            size_mb = (page_size * page_count) / 1_048_576
        except sqlite3.Error:
            logger.exception("PRAGMA query failed")
            integrity = journal = "?"
            size_mb = 0.0
        stats.append(("integrity_check", integrity, ""))
        stats.append(("journal_mode", journal, ""))
        stats.append(("size_mb", f"{size_mb:.2f}", ""))
        stats.append(("db_path", getattr(self.ctx.db, "path", "?"), ""))
        _show_table(self.ctx.parent, "Database health",
                    ("metric", "value", "note"), stats,
                    widths=[220, 500, 200])
        audit(self.ctx, "db_health", "db", "",
              f"size_mb={size_mb:.2f}")


# ===========================================================================
# Service container + feature registry
# ===========================================================================

@dataclass
class AdminServices:
    """Aggregates every service the Admin Tools tab needs."""
    data: AttendanceDataService
    requests: RequestWorkflowService
    policy: PolicyService
    reporting: ReportingService
    notifications: NotificationService
    integrations: IntegrationService
    bulk: BulkOperationsService
    security: SecurityAuditService
    diagnostics: DiagnosticsService

    @classmethod
    def for_context(cls, ctx: AdminContext) -> "AdminServices":
        student_picker = StudentPicker(ctx)
        module_picker = ModulePicker(ctx)
        return cls(
            data          = AttendanceDataService(ctx, module_picker),
            requests      = RequestWorkflowService(ctx, module_picker),
            policy        = PolicyService(ctx, module_picker),
            reporting     = ReportingService(ctx),
            notifications = NotificationService(ctx, student_picker,
                                                module_picker),
            integrations  = IntegrationService(ctx, student_picker,
                                                module_picker),
            bulk          = BulkOperationsService(ctx, student_picker,
                                                  module_picker),
            security      = SecurityAuditService(ctx, student_picker),
            diagnostics   = DiagnosticsService(ctx),
        )


@dataclass(frozen=True)
class FeatureSpec:
    number: int
    category: str
    label: str
    method: Callable[[AdminServices], Callable[[], None]]


def _build_feature_registry() -> list[FeatureSpec]:
    return [
        # Data
        FeatureSpec( 1, "Data", "Bulk import CSV",
                    lambda s: s.data.bulk_import_csv),
        FeatureSpec( 2, "Data", "Bulk export CSV",
                    lambda s: s.data.bulk_export_csv),
        FeatureSpec( 3, "Data", "Edit record in place",
                    lambda s: s.data.edit_attendance_row),
        FeatureSpec( 4, "Data", "Undo delete (24h trash)",
                    lambda s: s.data.undo_recent_deletes),
        FeatureSpec( 5, "Data", "Merge duplicate rows",
                    lambda s: s.data.merge_duplicate_rows),
        FeatureSpec( 6, "Data", "Correction audit log",
                    lambda s: s.data.show_correction_audit),
        FeatureSpec( 7, "Data", "Lock past dates",
                    lambda s: s.data.lock_past_dates),
        # Requests
        FeatureSpec( 8, "Requests", "Bulk approve / reject",
                    lambda s: s.requests.bulk_approve_or_reject),
        FeatureSpec( 9, "Requests", "Attach document to request",
                    lambda s: s.requests.attach_document_to_request),
        FeatureSpec(10, "Requests", "Auto-expire old pending",
                    lambda s: s.requests.expire_old_pending_requests),
        FeatureSpec(11, "Requests", "Delegate approval",
                    lambda s: s.requests.delegate_approval_authority),
        FeatureSpec(12, "Requests", "Comment thread on request",
                    lambda s: s.requests.show_request_comment_thread),
        FeatureSpec(13, "Requests", "Manage request templates",
                    lambda s: s.requests.manage_request_templates),
        # Policies
        FeatureSpec(14, "Policies", "Per-module policy",
                    lambda s: s.policy.edit_module_policy),
        FeatureSpec(15, "Policies", "Default university policy",
                    lambda s: s.policy.set_default_min_percent),
        FeatureSpec(16, "Policies", "Status vocabulary",
                    lambda s: s.policy.manage_status_vocabulary),
        FeatureSpec(17, "Policies", "Auto-excuse rules",
                    lambda s: s.policy.add_auto_excuse_rule),
        FeatureSpec(18, "Policies", "Global grace period",
                    lambda s: s.policy.set_global_grace_minutes),
        # Reports
        FeatureSpec(19, "Reports", "At-risk students",
                    lambda s: s.reporting.show_at_risk_students),
        FeatureSpec(20, "Reports", "Module health",
                    lambda s: s.reporting.show_module_health),
        FeatureSpec(21, "Reports", "Cohort comparison",
                    lambda s: s.reporting.compare_cohorts),
        FeatureSpec(22, "Reports", "Weekly trend",
                    lambda s: s.reporting.show_weekly_trend),
        FeatureSpec(23, "Reports", "Term-over-term",
                    lambda s: s.reporting.compare_terms),
        FeatureSpec(24, "Reports", "Schedule recurring report",
                    lambda s: s.reporting.schedule_recurring_report),
        FeatureSpec(25, "Reports", "Top consecutive absences",
                    lambda s: s.reporting.show_top_absentees),
        FeatureSpec(26, "Reports", "Day-of-week heatmap",
                    lambda s: s.reporting.show_dayofweek_heatmap),
        # Notifications
        FeatureSpec(27, "Notifications", "Threshold alerts",
                    lambda s: s.notifications.create_threshold_alerts),
        FeatureSpec(28, "Notifications", "Parent notifications",
                    lambda s: s.notifications.notify_parents_for_student),
        FeatureSpec(29, "Notifications", "Bulk announcement",
                    lambda s: s.notifications.post_bulk_announcement),
        FeatureSpec(30, "Notifications", "SMS fallback queue",
                    lambda s: s.notifications.queue_sms_fallback),
        # Integrations
        FeatureSpec(31, "Integrations", "Calendar events link",
                    lambda s: s.integrations.show_upcoming_calendar_events),
        FeatureSpec(32, "Integrations", "Module schedule sessions",
                    lambda s: s.integrations.show_module_schedule),
        FeatureSpec(33, "Integrations", "Feed student risk model",
                    lambda s: s.integrations.feed_student_risk_assessment),
        FeatureSpec(34, "Integrations", "Grade penalty candidates",
                    lambda s: s.integrations.show_grade_penalty_candidates),
        FeatureSpec(35, "Integrations", "Wellbeing cross-reference",
                    lambda s: s.integrations.show_absences_vs_mood),
        FeatureSpec(36, "Integrations", "Raise disciplinary action",
                    lambda s: s.integrations.raise_disciplinary_action),
        FeatureSpec(37, "Integrations", "Scholarship attendance check",
                    lambda s: s.integrations.show_scholarship_attendance_check),
        # Bulk
        FeatureSpec(38, "Bulk", "Mark whole class present",
                    lambda s: s.bulk.mark_module_all_present),
        FeatureSpec(39, "Bulk", "Copy previous day",
                    lambda s: s.bulk.copy_previous_day_roll),
        FeatureSpec(40, "Bulk", "Recurring absence",
                    lambda s: s.bulk.create_recurring_absence),
        FeatureSpec(41, "Bulk", "Reassign records on transfer",
                    lambda s: s.bulk.reassign_records_on_transfer),
        # Security
        FeatureSpec(42, "Security", "Permission matrix",
                    lambda s: s.security.show_permission_matrix),
        FeatureSpec(43, "Security", "Full audit trail",
                    lambda s: s.security.show_full_audit_trail),
        FeatureSpec(44, "Security", "Impersonate (read-only)",
                    lambda s: s.security.impersonate_user_readonly),
        FeatureSpec(45, "Security", "Retention purge",
                    lambda s: s.security.purge_per_retention_policy),
        FeatureSpec(46, "Security", "GDPR subject export",
                    lambda s: s.security.gdpr_subject_export),
        # Diagnostics
        FeatureSpec(47, "Diagnostics", "Orphan attendance rows",
                    lambda s: s.diagnostics.show_orphan_attendance_rows),
        FeatureSpec(48, "Diagnostics", "Missing sessions",
                    lambda s: s.diagnostics.show_modules_without_attendance),
        FeatureSpec(49, "Diagnostics", "Enrollment mismatch",
                    lambda s: s.diagnostics.show_enrollment_mismatches),
        FeatureSpec(50, "Diagnostics", "Database health",
                    lambda s: s.diagnostics.show_database_health),
    ]


FEATURES: list[FeatureSpec] = _build_feature_registry()


# ===========================================================================
# Soft-delete override + tab renderer
# ===========================================================================

def install_soft_delete(db) -> None:
    """Wrap Database.delete_absence so deletions land in the 24h trash."""
    if getattr(db, "_soft_delete_installed", False):
        return
    original = db.delete_absence

    def soft_delete(absence_id: int) -> None:
        try:
            row = db.cur.execute(
                """SELECT id, student_id, module_code, date, status, reason
                   FROM attendance WHERE id=?""", (absence_id,)).fetchone()
            if row:
                payload = json.dumps({
                    "id": row[0], "student_id": row[1],
                    "module_code": row[2], "date": row[3],
                    "status": row[4], "reason": row[5],
                })
                db.cur.execute(
                    """INSERT INTO abs_tracker_trash
                       (deleted_by, original_table, original_id, payload)
                       VALUES (?, 'attendance', ?, ?)""",
                    ("admin", row[0], payload))
        except sqlite3.Error:
            logger.exception("soft-delete snapshot failed id=%s", absence_id)
        original(absence_id)

    db.delete_absence = soft_delete
    db._soft_delete_installed = True


def build_admin_tab(notebook: ttk.Notebook, ctx: AdminContext) -> None:
    """Render all 50 features into a dedicated Admin Tools tab."""
    try:
        ensure_support_tables(ctx.db)
        install_soft_delete(ctx.db)
    except sqlite3.Error:
        logger.exception("could not initialise admin tools")
        messagebox.showerror(
            "Admin Tools",
            "Could not initialise admin-tools tables. See log.",
            parent=ctx.parent)
        return

    services = AdminServices.for_context(ctx)

    frame = ttk.Frame(notebook)
    notebook.add(frame, text="🛠 Admin Tools (50)")

    canvas = tk.Canvas(frame, bg="#f0f4f8", highlightthickness=0)
    vsb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    canvas.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    inner = tk.Frame(canvas, bg="#f0f4f8")
    canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    by_cat: dict[str, list[FeatureSpec]] = {}
    for spec in FEATURES:
        by_cat.setdefault(spec.category, []).append(spec)

    for cat, items in by_cat.items():
        box = tk.LabelFrame(inner, text=cat, padx=10, pady=8,
                            font=("Arial", 11, "bold"), bg="#f0f4f8",
                            fg="#1e3a5f")
        box.pack(fill="x", padx=12, pady=8)
        cols = 3
        for i, spec in enumerate(items):
            try:
                callback = spec.method(services)
            except Exception:
                logger.exception("feature %d binding failed", spec.number)
                continue
            btn = tk.Button(
                box, text=f"{spec.number:02d}. {spec.label}",
                command=callback,
                bg="#2563eb", fg="white", activebackground="#1d4ed8",
                relief="flat", cursor="hand2",
                width=32, anchor="w", padx=8, pady=6,
            )
            btn.grid(row=i // cols, column=i % cols, padx=4, pady=3, sticky="w")

    logger.info("admin tools tab built (%d features)", len(FEATURES))


# ===========================================================================
# Backwards-compat: keep module-level callable aliases for any external caller
# that imported the old `feat_NN_*` names directly.
# ===========================================================================

def _wrap(method_picker: Callable[[AdminServices], Callable[[], None]]
          ) -> Callable[[AdminContext], None]:
    def runner(ctx: AdminContext) -> None:
        services = AdminServices.for_context(ctx)
        method_picker(services)()
    return runner


_LEGACY_ALIASES: dict[str, Callable] = {
    "feat_01_bulk_import":            _wrap(lambda s: s.data.bulk_import_csv),
    "feat_02_bulk_export":            _wrap(lambda s: s.data.bulk_export_csv),
    "feat_03_edit_record":            _wrap(lambda s: s.data.edit_attendance_row),
    "feat_04_undo_delete":            _wrap(lambda s: s.data.undo_recent_deletes),
    "feat_05_merge_duplicates":       _wrap(lambda s: s.data.merge_duplicate_rows),
    "feat_06_correction_audit":       _wrap(lambda s: s.data.show_correction_audit),
    "feat_07_lock_past_dates":        _wrap(lambda s: s.data.lock_past_dates),
    "feat_08_bulk_approve_reject":    _wrap(lambda s: s.requests.bulk_approve_or_reject),
    "feat_09_request_attachment":     _wrap(lambda s: s.requests.attach_document_to_request),
    "feat_10_expire_pending":         _wrap(lambda s: s.requests.expire_old_pending_requests),
    "feat_11_delegate_approval":      _wrap(lambda s: s.requests.delegate_approval_authority),
    "feat_12_request_comment_thread": _wrap(lambda s: s.requests.show_request_comment_thread),
    "feat_13_request_templates":      _wrap(lambda s: s.requests.manage_request_templates),
    "feat_14_module_policy":          _wrap(lambda s: s.policy.edit_module_policy),
    "feat_15_default_policy":         _wrap(lambda s: s.policy.set_default_min_percent),
    "feat_16_status_vocabulary":      _wrap(lambda s: s.policy.manage_status_vocabulary),
    "feat_17_auto_excuse_rules":      _wrap(lambda s: s.policy.add_auto_excuse_rule),
    "feat_18_grace_period":           _wrap(lambda s: s.policy.set_global_grace_minutes),
    "feat_19_at_risk":                _wrap(lambda s: s.reporting.show_at_risk_students),
    "feat_20_module_health":          _wrap(lambda s: s.reporting.show_module_health),
    "feat_21_cohort_compare":         _wrap(lambda s: s.reporting.compare_cohorts),
    "feat_22_trend_chart":            _wrap(lambda s: s.reporting.show_weekly_trend),
    "feat_23_term_compare":           _wrap(lambda s: s.reporting.compare_terms),
    "feat_24_schedule_report":        _wrap(lambda s: s.reporting.schedule_recurring_report),
    "feat_25_consecutive_absences":   _wrap(lambda s: s.reporting.show_top_absentees),
    "feat_26_heatmap":                _wrap(lambda s: s.reporting.show_dayofweek_heatmap),
    "feat_27_threshold_alerts":       _wrap(lambda s: s.notifications.create_threshold_alerts),
    "feat_28_parent_notifications":   _wrap(lambda s: s.notifications.notify_parents_for_student),
    "feat_29_bulk_announcement":      _wrap(lambda s: s.notifications.post_bulk_announcement),
    "feat_30_sms_fallback":           _wrap(lambda s: s.notifications.queue_sms_fallback),
    "feat_31_calendar_link":          _wrap(lambda s: s.integrations.show_upcoming_calendar_events),
    "feat_32_schedule_sessions":      _wrap(lambda s: s.integrations.show_module_schedule),
    "feat_33_risk_feed":              _wrap(lambda s: s.integrations.feed_student_risk_assessment),
    "feat_34_grade_link":             _wrap(lambda s: s.integrations.show_grade_penalty_candidates),
    "feat_35_wellbeing_link":         _wrap(lambda s: s.integrations.show_absences_vs_mood),
    "feat_36_disciplinary_action":    _wrap(lambda s: s.integrations.raise_disciplinary_action),
    "feat_37_finance_link":           _wrap(lambda s: s.integrations.show_scholarship_attendance_check),
    "feat_38_bulk_mark_present":      _wrap(lambda s: s.bulk.mark_module_all_present),
    "feat_39_copy_previous_day":      _wrap(lambda s: s.bulk.copy_previous_day_roll),
    "feat_40_recurring_absence":      _wrap(lambda s: s.bulk.create_recurring_absence),
    "feat_41_reassign_records":       _wrap(lambda s: s.bulk.reassign_records_on_transfer),
    "feat_42_permission_matrix":      _wrap(lambda s: s.security.show_permission_matrix),
    "feat_43_full_audit_trail":       _wrap(lambda s: s.security.show_full_audit_trail),
    "feat_44_impersonate":            _wrap(lambda s: s.security.impersonate_user_readonly),
    "feat_45_retention_purge":        _wrap(lambda s: s.security.purge_per_retention_policy),
    "feat_46_gdpr_export":            _wrap(lambda s: s.security.gdpr_subject_export),
    "feat_47_orphan_rows":            _wrap(lambda s: s.diagnostics.show_orphan_attendance_rows),
    "feat_48_missing_sessions":       _wrap(lambda s: s.diagnostics.show_modules_without_attendance),
    "feat_49_enrollment_mismatch":    _wrap(lambda s: s.diagnostics.show_enrollment_mismatches),
    "feat_50_db_health":              _wrap(lambda s: s.diagnostics.show_database_health),
}
globals().update(_LEGACY_ALIASES)
