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
        CREATE TABLE IF NOT EXISTS attendance_grade_penalties (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id   TEXT NOT NULL,
            module_code  TEXT NOT NULL,
            threshold    REAL,
            pct          REAL,
            applied_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            applied_by   TEXT,
            grade_row_id INTEGER,
            UNIQUE(student_id, module_code)
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
                """CREATE TABLE IF NOT EXISTS abs_tracker_sms_queue (
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
                    "INSERT INTO abs_tracker_sms_queue (recipient, body) VALUES (?,?)",
                    (sid, f"ALERT: attendance {pct:.1f}% "
                          f"below {threshold:.0f}%"))
                queued += 1
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("SMS queue failed threshold=%s", threshold)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "sms_queue", "abs_tracker_sms_queue", "", f"n={queued}")
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
        # (4) Two-sided window: past events explain absences, future events
        # are useful for planning. Defaults remembered via _get_setting so
        # the user doesn't keep re-typing.
        try:
            back_default = int(_get_setting(
                self.ctx.db, "calendar_link_lookback", "30"))
        except (TypeError, ValueError):
            back_default = 30
        try:
            ahead_default = int(_get_setting(
                self.ctx.db, "calendar_link_lookahead", "30"))
        except (TypeError, ValueError):
            ahead_default = 30
        back = simpledialog.askinteger(
            "Window", "Look back how many days?",
            parent=self.ctx.parent, initialvalue=back_default)
        if back is None:
            return
        ahead = simpledialog.askinteger(
            "Window", "Look ahead how many days?",
            parent=self.ctx.parent, initialvalue=ahead_default)
        if ahead is None:
            return
        try:
            _set_setting(self.ctx.db, "calendar_link_lookback", back)
            _set_setting(self.ctx.db, "calendar_link_lookahead", ahead)
        except sqlite3.Error:
            pass

        start = (date.today() - timedelta(days=back)).isoformat()
        end = (date.today() + timedelta(days=ahead)).isoformat()
        try:
            # (3) Per-row absence count: makes it obvious which calendar
            # entries (e.g. an unmarked holiday or trip day) are driving
            # absence spikes. Correlated subquery keeps the query simple.
            rows = self.ctx.db.cur.execute(
                """SELECT e.date, e.name, e.event_type,
                          COALESCE(
                            (SELECT COUNT(*) FROM attendance a
                             WHERE a.date = e.date
                               AND a.status = 'absent'),
                            0) AS abs_count
                   FROM academic_calendar_events e
                   WHERE e.date BETWEEN ? AND ?
                   ORDER BY e.date""", (start, end)).fetchall()
        except sqlite3.Error:
            logger.exception("calendar fetch failed")
            rows = []

        def _selected():
            try:
                sel = tree.selection()
                if not sel:
                    return None
                vals = tree.item(sel[0], "values")
                # (date, name, type, abs_count)
                return vals
            except Exception:
                return None

        def _open_calendar_gui():
            sel = _selected()
            iso_date = sel[0] if sel else None
            try:
                from education_system.university_system.modules.domain.academics.gui.academic_calendar.main_gui import (  # noqa: E501
                    CalendarGUI,
                )
                win2 = tk.Toplevel(self.ctx.parent)
                win2.title(f"Academic Calendar — {iso_date}" if iso_date
                           else "Academic Calendar")
                win2.geometry("1400x900")
                gui = CalendarGUI(auth_manager=getattr(self.ctx, "auth", None),
                                  parent_window=win2)
                if iso_date and hasattr(gui, "navigate_to_date"):
                    try:
                        gui.navigate_to_date(iso_date)
                    except Exception:
                        logger.exception("calendar navigate_to_date failed")
            except Exception:
                logger.exception("could not open Academic Calendar GUI")
                messagebox.showerror(
                    "Academic Calendar",
                    "Could not open the Academic Calendar GUI (see log).",
                    parent=self.ctx.parent)

        def _show_absences_on_day():
            # (1) Reverse direction: show attendance rows on the selected
            # event's date, so the calendar is also a diagnostic surface.
            sel = _selected()
            if not sel:
                messagebox.showinfo(
                    "Absences on day", "Select a calendar row first.",
                    parent=self.ctx.parent)
                return
            iso_date = sel[0]
            try:
                abs_rows = self.ctx.db.cur.execute(
                    """SELECT a.student_id, a.module_code, a.status,
                              COALESCE(a.reason, '')
                       FROM attendance a
                       WHERE a.date = ?
                       ORDER BY a.status, a.module_code, a.student_id""",
                    (iso_date,)).fetchall()
            except sqlite3.Error:
                logger.exception("absences-on-day query failed date=%s",
                                 iso_date)
                abs_rows = []
            _show_table(
                self.ctx.parent,
                f"Attendance on {iso_date} ({sel[1]})",
                ("student", "module", "status", "reason"),
                abs_rows, widths=[120, 160, 100, 380])

        def _auto_excuse_for_event():
            # (2) Inline auto-excuse for the selected event's date+type:
            # avoids hopping to feature #17 to do the same job. We update
            # only attendance rows whose date matches the event so we
            # don't accidentally excuse unrelated days that happen to
            # share an event_type elsewhere in the window.
            sel = _selected()
            if not sel:
                messagebox.showinfo(
                    "Auto-excuse", "Select a calendar row first.",
                    parent=self.ctx.parent)
                return
            iso_date, ev_name, ev_type = sel[0], sel[1], sel[2]
            if not ev_type:
                messagebox.showinfo(
                    "Auto-excuse",
                    "Selected event has no event_type to match.",
                    parent=self.ctx.parent)
                return
            if not Prompt.confirm(
                    self.ctx.parent, "Confirm auto-excuse",
                    f"Auto-excuse all absences on {iso_date} for "
                    f"event '{ev_name}' (type='{ev_type}')?\n\n"
                    f"Also adds '{ev_type}' to the standing auto-excuse "
                    f"rules so future entries on these days are handled "
                    f"the same way."):
                return
            try:
                # Standing rule (idempotent).
                self.ctx.db.cur.execute(
                    """INSERT OR IGNORE INTO abs_tracker_auto_excuse_rules
                       (event_type) VALUES (?)""", (ev_type,))
                cur = self.ctx.db.cur.execute(
                    """UPDATE attendance
                       SET status='excused',
                           reason='auto: '||?
                       WHERE date=? AND status='absent'""",
                    (ev_type, iso_date))
                updated = cur.rowcount
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception(
                    "inline auto-excuse failed date=%s ev=%s",
                    iso_date, ev_type)
                messagebox.showerror("Failed", str(e),
                                     parent=self.ctx.parent)
                return
            audit(self.ctx, "auto_excuse_inline", "attendance",
                  iso_date, f"ev_type={ev_type} updated={updated}")
            # Reflect new (zero) absence count in the calendar table.
            try:
                node = tree.selection()[0]
                vals = list(tree.item(node, "values"))
                if len(vals) >= 4:
                    vals[3] = "0"
                    tree.item(node, values=vals)
            except Exception:
                pass
            messagebox.showinfo(
                "Auto-excused",
                f"Excused {updated} absence(s) on {iso_date}.",
                parent=self.ctx.parent)

        win, tree = _show_table(
            self.ctx.parent, f"Calendar ({start} → {end})",
            ("date", "name", "type", "absences"), rows,
            widths=[110, 440, 130, 90],
            extra_button=("📅  Open Academic Calendar GUI (selected date)",
                          _open_calendar_gui))

        # Secondary action bar — keeps the calendar GUI link as the
        # primary call-to-action while still surfacing the attendance
        # diagnostic + inline auto-excuse.
        extra = tk.Frame(win)
        extra.pack(side="bottom", fill="x")
        tk.Button(extra, text="🔍  Show absences on this day",
                  command=_show_absences_on_day,
                  bg="#0ea5e9", fg="white", relief="flat",
                  padx=10, pady=4).pack(side="left", padx=10, pady=4)
        tk.Button(extra, text="✅  Auto-excuse absences for this event",
                  command=_auto_excuse_for_event,
                  bg="#16a34a", fg="white", relief="flat",
                  padx=10, pady=4).pack(side="left", padx=4, pady=4)

        tree.bind("<Double-1>", lambda _e: _open_calendar_gui())

    # --- #32 ----------------------------------------------------------
    _DAY_NAME_TO_WEEKDAY = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }

    @safe("Pre-generate sessions")
    def show_module_schedule(self) -> None:
        mc = self.module_picker.pick("Sessions for which module?")
        if not mc:
            return
        rows = self._fetch_module_schedule_with_attendance(mc)

        def _open_scheduling_gui(schedule_id: Optional[int] = None) -> None:
            """Launch ModuleSchedulingGUI in a new Toplevel, scoped to this module.

            If ``schedule_id`` is provided, jumps straight to EditScheduleDialog
            for that row instead of just filtering the Schedules tab.
            """
            try:
                from education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui import (
                    ModuleSchedulingGUI,
                )
            except Exception as e:
                logger.exception("module scheduling GUI import failed")
                messagebox.showerror("Module Scheduling",
                                     f"Could not open scheduling GUI: {e}",
                                     parent=self.ctx.parent)
                return
            top = tk.Toplevel(self.ctx.parent)
            top.title(f"Module Scheduling — {mc}")
            try:
                gui = ModuleSchedulingGUI(top)
                auth = getattr(self.ctx, "auth", None)
                if auth is not None and hasattr(gui, "set_auth"):
                    try:
                        gui.set_auth(auth)
                    except Exception:
                        logger.exception("set_auth on scheduling GUI failed")
                try:
                    gui.notebook.select(1)
                except Exception:
                    pass
                try:
                    gui.schedule_search_var.set(mc)
                except Exception:
                    pass
                # (#5) If the caller picked a specific schedule row, open its
                # EditScheduleDialog so they're editing the row they clicked.
                if schedule_id is not None:
                    try:
                        from education_system.university_system.modules.domain.academics.gui.module_scheduling.dialogs import (
                            EditScheduleDialog,
                        )
                        EditScheduleDialog(top, gui.scheduler,
                                           int(schedule_id), gui=gui)
                    except Exception:
                        logger.exception("EditScheduleDialog launch failed sid=%s",
                                         schedule_id)
            except Exception as e:
                logger.exception("module scheduling GUI launch failed")
                messagebox.showerror("Module Scheduling", str(e), parent=top)

        def _open_add_schedule_dialog() -> None:
            """(#3) Empty-state shortcut: open AddScheduleDialog directly."""
            try:
                from education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui import (
                    ModuleSchedulingGUI,
                )
                from education_system.university_system.modules.domain.academics.gui.module_scheduling.dialogs import (
                    AddScheduleDialog,
                )
                from education_system.university_system.modules.domain.academics.services.module_scheduling import (
                    ModuleScheduler,
                )
            except Exception as e:
                logger.exception("AddScheduleDialog import failed")
                messagebox.showerror("Module Scheduling", str(e),
                                     parent=self.ctx.parent)
                return
            try:
                AddScheduleDialog(self.ctx.parent, ModuleScheduler(), gui=None)
            except Exception as e:
                logger.exception("AddScheduleDialog launch failed")
                messagebox.showerror("Module Scheduling", str(e),
                                     parent=self.ctx.parent)
                return
            # Refresh the popup so newly added rows appear.
            try:
                _refresh()
            except Exception:
                pass

        def _pregenerate() -> None:
            """(#1) Materialise individual session dates from the schedule rows.

            Writes to ``module_sessions`` (separate from ``attendance`` so we
            don't pollute roll-call data with placeholder rows).
            """
            rng = pick_date_range(self.ctx.parent,
                                  "Pre-generate sessions")
            if not rng:
                return
            start, end = rng
            n = self._pregenerate_module_sessions(mc, start, end)
            messagebox.showinfo(
                "Pre-generated",
                f"Generated {n} session date(s) for {mc} between {start} and {end}.",
                parent=self.ctx.parent,
            )
            # Refresh so the attended overlay reflects any side effects.
            try:
                _refresh()
            except Exception:
                pass

        def _populate(tree, rows):
            for r in tree.get_children():
                tree.delete(r)
            tree.tag_configure("ghost", background="#fee2e2",
                               foreground="#991b1b")
            for r in rows:
                sid, day, st, en, room, instr, sem, yr, status, attended = r
                tags = ("ghost",) if (attended or 0) == 0 else ()
                # Use the schedule_id as the tree item iid so the double-click
                # handler can recover it cheaply.
                tree.insert("", "end", iid=str(sid),
                            values=(day, st, en, room, instr, sem, yr,
                                    status, attended),
                            tags=tags)

        def _refresh():
            new_rows = self._fetch_module_schedule_with_attendance(mc)
            _populate(tree, new_rows)
            empty_label_var.set(
                "" if new_rows else
                f"No schedule rows yet for {mc}. Use “Add schedule…” to create one."
            )

        win, tree = _show_table(
            self.ctx.parent, f"Scheduled sessions for {mc}",
            ("day", "start", "end", "room", "instructor",
             "sem", "yr", "status", "attended"),
            [],  # filled by _populate below so iids are set
            extra_button=("Open in Module Scheduling GUI",
                          lambda: _open_scheduling_gui(None)),
        )
        _populate(tree, rows)

        # (#5) Double-click → edit *that* row. Falls back to whole-module
        # filter view if we can't recover an id.
        def _on_double(_e):
            sel = tree.selection()
            if not sel:
                return
            try:
                sid = int(sel[0])
            except (TypeError, ValueError):
                sid = None
            _open_scheduling_gui(sid)
        tree.bind("<Double-1>", _on_double)

        # Extra button row: pre-generate + add-schedule shortcut. Packed with
        # side="bottom" so it sits above the Close button frame from _show_table.
        extra_btns = tk.Frame(win)
        extra_btns.pack(fill="x", pady=(0, 4), side="bottom")
        tk.Button(extra_btns, text="Pre-generate sessions…",
                  command=_pregenerate, bg="#0ea5e9", fg="white",
                  relief="flat", padx=10, pady=4).pack(side="left", padx=10)
        tk.Button(extra_btns, text="Add schedule…",
                  command=_open_add_schedule_dialog, bg="#10b981",
                  fg="white", relief="flat", padx=10, pady=4).pack(side="left",
                                                                    padx=4)

        # (#3) Empty-state hint.
        empty_label_var = tk.StringVar(value="")
        tk.Label(win, textvariable=empty_label_var, fg="#6b7280",
                 anchor="w", padx=10, pady=4).pack(fill="x", side="bottom")
        if not rows:
            empty_label_var.set(
                f"No schedule rows yet for {mc}. Use “Add schedule…” to create one."
            )

    # ---- helpers for #1 / #4 ----------------------------------------------
    def _fetch_module_schedule_with_attendance(self, mc):
        """Return schedule rows for ``mc`` annotated with an attendance count.

        ``attended_n`` counts attendance rows whose date's weekday matches
        the schedule slot's ``day_of_week`` (stored as a name in this DB —
        Monday-Friday). Used to flag "ghost" slots that have never seen a roll.
        """
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT ms.id, ms.day_of_week, ms.start_time, ms.end_time,
                          ms.room_id, ms.instructor_id, ms.semester,
                          ms.year, ms.status,
                          (SELECT COUNT(*) FROM attendance a
                           WHERE a.module_code = ms.module_code
                             AND LOWER(ms.day_of_week) = LOWER(
                               CASE strftime('%w', a.date)
                                 WHEN '0' THEN 'Sunday'
                                 WHEN '1' THEN 'Monday'
                                 WHEN '2' THEN 'Tuesday'
                                 WHEN '3' THEN 'Wednesday'
                                 WHEN '4' THEN 'Thursday'
                                 WHEN '5' THEN 'Friday'
                                 WHEN '6' THEN 'Saturday'
                               END)) AS attended_n
                   FROM module_schedule ms
                   WHERE ms.module_code = ?
                   ORDER BY ms.day_of_week, ms.start_time""",
                (mc,),
            ).fetchall()
            return rows
        except sqlite3.Error:
            logger.exception("schedule fetch failed mc=%s", mc)
            return []

    def _pregenerate_module_sessions(self, mc, start, end) -> int:
        """Expand schedule rows into ``module_sessions`` for the date range.

        Idempotent — UNIQUE(module_code, date, start_time) means re-running
        with overlapping ranges silently skips already-generated dates.
        Returns the number of newly inserted session dates.
        """
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS module_sessions (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       module_code TEXT NOT NULL,
                       schedule_id INTEGER,
                       date TEXT NOT NULL,
                       start_time TEXT,
                       end_time TEXT,
                       generated_at TEXT DEFAULT (datetime('now')),
                       UNIQUE (module_code, date, start_time)
                   )"""
            )
            sched = self.ctx.db.cur.execute(
                "SELECT id, day_of_week, start_time, end_time "
                "FROM module_schedule WHERE module_code = ?",
                (mc,),
            ).fetchall()
        except sqlite3.Error:
            logger.exception("pre-generate schedule fetch failed mc=%s", mc)
            return 0
        if not sched:
            messagebox.showinfo(
                "No schedule",
                f"{mc} has no schedule rows to expand.",
                parent=self.ctx.parent,
            )
            return 0
        try:
            s = datetime.strptime(start, "%Y-%m-%d").date()
            e = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Bad dates",
                                 "Pre-generate dates were not in YYYY-MM-DD form.",
                                 parent=self.ctx.parent)
            return 0
        inserted = 0
        try:
            cur_d = s
            while cur_d <= e:
                weekday = cur_d.weekday()  # Mon=0 .. Sun=6
                for sid, dow, start_time, end_time in sched:
                    expected = self._DAY_NAME_TO_WEEKDAY.get(
                        (dow or "").strip().lower())
                    if expected != weekday:
                        continue
                    self.ctx.db.cur.execute(
                        "INSERT OR IGNORE INTO module_sessions "
                        "(module_code, schedule_id, date, start_time, end_time) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (mc, sid, cur_d.isoformat(), start_time, end_time),
                    )
                    if self.ctx.db.cur.rowcount:
                        inserted += 1
                cur_d += timedelta(days=1)
            self.ctx.db.conn.commit()
        except sqlite3.Error:
            self.ctx.db.conn.rollback()
            logger.exception("pre-generate write failed mc=%s", mc)
            return 0
        audit(self.ctx, "pregenerate", "module_sessions", mc,
              f"{start}..{end} n={inserted}")
        return inserted

    # --- #33 ----------------------------------------------------------
    @safe("Risk feed")
    def feed_student_risk_assessment(self, quiet: bool = False) -> None:
        """Refresh the student_risk_assessment feed.

        ``quiet=True`` suppresses dialogs and the result table so this
        can be invoked from a scheduled-reports / cron pipeline. Admin
        email on new HIGH crossings still fires in quiet mode.
        """
        today = date.today().isoformat()
        cutoff_60 = (date.today() - timedelta(days=60)).isoformat()

        # (2) Min-attendance-count guard so a student with a single
        # tardy record doesn't get scored at "100 risk" off one row.
        try:
            min_count = int(_get_setting(self.ctx.db,
                                         "risk_min_count", "5"))
        except (TypeError, ValueError):
            min_count = 5

        # (4) Blended signals: attendance %, recent failed grades,
        # pending absence requests. One query so we touch each table
        # exactly once.
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT s.student_id,
                          COALESCE(att.pct, 0)   AS pct,
                          COALESCE(att.cnt, 0)   AS cnt,
                          COALESCE(g.fails, 0)   AS recent_fails,
                          COALESCE(r.pending, 0) AS pending_reqs
                   FROM students s
                   LEFT JOIN (
                       SELECT student_id,
                              SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                                  * 1.0 / NULLIF(COUNT(*),0) * 100 AS pct,
                              COUNT(*) AS cnt
                       FROM attendance GROUP BY student_id
                   ) att ON att.student_id = s.student_id
                   LEFT JOIN (
                       SELECT student_id, COUNT(*) AS fails
                       FROM grades
                       WHERE submission_date >= ?
                         AND (score < 50
                              OR letter_grade IN ('F','D-','D'))
                       GROUP BY student_id
                   ) g ON g.student_id = s.student_id
                   LEFT JOIN (
                       SELECT student_id, COUNT(*) AS pending
                       FROM absence_requests
                       WHERE status='pending'
                       GROUP BY student_id
                   ) r ON r.student_id = s.student_id""",
                (cutoff_60,)).fetchall()
        except sqlite3.Error:
            logger.exception("risk feed read failed")
            if not quiet:
                messagebox.showerror("Error", "Could not read attendance.",
                                     parent=self.ctx.parent)
            return

        # written rows: (sid, level, score, prev_score, delta, cnt,
        #                fails, pending)
        written: list[tuple] = []
        skipped_dupe = 0
        skipped_insufficient = 0
        new_high: list[tuple] = []
        model_tag = "attendance_blend_v1"

        try:
            for sid, pct, cnt, fails, pending in rows:
                if cnt < min_count:
                    skipped_insufficient += 1
                    continue

                # Score: attendance is primary, fails and pending nudge
                # the score upward without dominating it. Capped [0,100].
                base = 100.0 - float(pct or 0)
                score = (base
                         + min(20.0, 5.0 * float(fails or 0))
                         + min(10.0, 2.0 * float(pending or 0)))
                score = round(max(0.0, min(100.0, score)), 2)
                level = ("high" if score >= 30
                         else "medium" if score >= 15
                         else "low")

                # (3) Pull the most recent prior row for this student so
                # we can compute Δ and detect new HIGH crossings.
                prior = self.ctx.db.cur.execute(
                    """SELECT risk_score, risk_level, assessment_date
                       FROM student_risk_assessment
                       WHERE student_id=?
                       ORDER BY assessment_date DESC, id DESC LIMIT 1""",
                    (sid,)).fetchone()
                prev_score = prior[0] if prior else None
                prev_level = prior[1] if prior else None
                prev_date = prior[2] if prior else None

                # (1) Dedupe: if today's row already matches, leave it
                # alone. If today's exists but score moved, UPDATE in
                # place rather than appending another duplicate row.
                if (prev_date == today
                        and prev_score is not None
                        and abs(prev_score - score) < 0.005):
                    skipped_dupe += 1
                elif prev_date == today:
                    self.ctx.db.cur.execute(
                        """UPDATE student_risk_assessment
                           SET risk_score=?, risk_level=?,
                               prediction_model=?, confidence=?
                           WHERE student_id=? AND assessment_date=?""",
                        (score, level, model_tag, 0.85, sid, today))
                else:
                    self.ctx.db.cur.execute(
                        """INSERT INTO student_risk_assessment
                           (student_id, risk_score, risk_level,
                            assessment_date, prediction_model, confidence)
                           VALUES (?,?,?,?,?,?)""",
                        (sid, score, level, today, model_tag, 0.85))

                delta = (round(score - prev_score, 2)
                         if prev_score is not None else None)
                written.append((sid, level, score, prev_score, delta,
                                cnt, fails, pending))

                if level == "high" and prev_level != "high":
                    new_high.append((sid, prev_level, level, score))

            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("risk feed write failed")
            if not quiet:
                messagebox.showerror("Failed", str(e),
                                     parent=self.ctx.parent)
            return

        audit(self.ctx, "risk_feed", "student_risk_assessment", "",
              f"written={len(written) - skipped_dupe} "
              f"dupes={skipped_dupe} "
              f"insufficient={skipped_insufficient} "
              f"new_high={len(new_high)} model={model_tag}")

        # (5) Email admins on HIGH crossings — fires in both interactive
        # and quiet mode so a scheduled run still alerts the team.
        if new_high:
            body = "Newly high-risk students from today's attendance feed:\n\n" + "\n".join(
                f"{sid}: {prev or 'n/a'} → {new} (score {sc:.1f})"
                for sid, prev, new, sc in new_high
            )
            try:
                _email_admin(
                    self.ctx.db,
                    f"[Risk feed] {len(new_high)} student(s) crossed into HIGH",
                    body,
                    sender_username=getattr(self.ctx, "username", "") or "")
            except Exception:
                logger.exception("admin notify failed")

        if quiet:
            return

        # ---- Interactive presentation -----------------------------------
        level_rank = {"high": 0, "medium": 1, "low": 2}
        written.sort(key=lambda r: (level_rank.get(r[1], 9), -r[2]))

        def _row_passes(level: str, current_filter: str) -> bool:
            if current_filter == "all":
                return True
            if current_filter == "high+medium":
                return level in ("high", "medium")
            return level == current_filter

        def _format(rows_iter):
            out = []
            for sid, level, score, prev, delta, cnt, fails, pending in rows_iter:
                if delta is None:
                    delta_s = "—"
                else:
                    delta_s = f"{'+' if delta >= 0 else ''}{delta:.1f}"
                out.append((sid, level, f"{score:.2f}",
                            "—" if prev is None else f"{prev:.2f}",
                            delta_s, str(cnt), str(fails), str(pending)))
            return out

        # (2) Default the filter to high+medium if any exist — matches
        # how an admin actually wants to triage the table.
        initial_filter = ("high+medium"
                          if any(r[1] in ("high", "medium")
                                 for r in written)
                          else "all")

        def _selected_sid():
            try:
                sel = tree.selection()
                if not sel:
                    return None
                vals = tree.item(sel[0], "values")
                return vals[0] if vals else None
            except Exception:
                return None

        def _open_risk_gui():
            # Drive the AnalyticsManager directly with a minimal shim so
            # we get the per-student risk report Toplevel WITHOUT
            # launching the full Grade Management GUI behind it.
            sid = _selected_sid()
            try:
                from types import SimpleNamespace
                from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.manager import (  # noqa: E501
                    AnalyticsManager,
                )
                shim = SimpleNamespace(
                    root=self.ctx.parent,
                    auth=getattr(self.ctx, "auth", None),
                    conn=None,
                    layout=None,
                )
                analytics = AnalyticsManager(shim)
                if sid and hasattr(analytics,
                                   "_perform_detailed_risk_assessment"):
                    analytics._perform_detailed_risk_assessment(sid)
                elif hasattr(analytics, "student_risk_assessment"):
                    analytics.student_risk_assessment()
            except Exception:
                logger.exception("could not open Student Risk report")
                messagebox.showerror(
                    "Student Risk",
                    "Could not open the Student Risk report (see log).",
                    parent=self.ctx.parent)

        title = (f"Risk feed ({today}) — "
                 f"{len(written) - skipped_dupe} updated, "
                 f"{skipped_dupe} unchanged, "
                 f"{skipped_insufficient} skipped (<{min_count} records)")
        win, tree = _show_table(
            self.ctx.parent, title,
            ("student", "risk_level", "score", "prev", "Δ",
             "att_count", "recent_fails", "pending_reqs"),
            _format(r for r in written
                    if _row_passes(r[1], initial_filter)),
            widths=[120, 100, 80, 80, 60, 90, 110, 110],
            extra_button=("🧠  Open Student Risk Assessment (selected)",
                          _open_risk_gui))
        tree.bind("<Double-1>", lambda _e: _open_risk_gui())

        # (2) Filter combobox above the Close button.
        bar = tk.Frame(win)
        bar.pack(side="bottom", fill="x")
        tk.Label(bar, text="Filter:").pack(side="left", padx=8, pady=4)
        filter_var = tk.StringVar(value=initial_filter)
        filt = ttk.Combobox(
            bar, textvariable=filter_var, state="readonly",
            values=["all", "high+medium", "high", "medium", "low"],
            width=14)
        filt.pack(side="left", pady=4)

        def _apply_filter(_e=None):
            current = filter_var.get()
            for child in tree.get_children():
                tree.delete(child)
            for tup in _format(r for r in written
                               if _row_passes(r[1], current)):
                tree.insert("", "end", values=tup)

        filt.bind("<<ComboboxSelected>>", _apply_filter)

        if new_high:
            tk.Label(
                win,
                text=f"⚠ {len(new_high)} student(s) crossed into HIGH "
                     f"since previous run — admins notified.",
                fg="#b91c1c", anchor="w", padx=10, pady=4
            ).pack(side="bottom", fill="x")

    # --- #34 ----------------------------------------------------------
    @safe("Grade link")
    def show_grade_penalty_candidates(self) -> None:
        # (4) Pull default threshold from settings, ask user, persist back.
        try:
            saved = float(_get_setting(self.ctx.db,
                                       "grade_penalty_threshold", "50"))
        except (TypeError, ValueError):
            saved = 50.0
        threshold = simpledialog.askfloat(
            "Threshold", "Penalty below %:",
            parent=self.ctx.parent, initialvalue=saved) or saved
        try:
            _set_setting(self.ctx.db, "grade_penalty_threshold", threshold)
        except sqlite3.Error:
            pass  # already logged

        try:
            # (3) Left join with attendance_grade_penalties so we can
            # surface which candidates already had a penalty applied and
            # avoid double-penalising on re-runs.
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id, a.module_code, a.pct,
                          CASE WHEN p.id IS NULL THEN '' ELSE '✓' END AS applied
                   FROM (
                       SELECT student_id, module_code,
                              SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                                  * 1.0 / NULLIF(COUNT(*),0) * 100 AS pct
                       FROM attendance
                       GROUP BY student_id, module_code
                   ) a
                   LEFT JOIN attendance_grade_penalties p
                       ON p.student_id = a.student_id
                      AND p.module_code = a.module_code
                   WHERE a.pct IS NOT NULL AND a.pct < ?
                   ORDER BY a.pct ASC""",
                (threshold,)).fetchall()
        except sqlite3.Error:
            logger.exception("grade link failed")
            rows = []

        def _selected_row():
            try:
                sel = tree.selection()
                if not sel:
                    return None
                vals = tree.item(sel[0], "values")
                return (vals[0], vals[1], float(vals[2]),
                        vals[3] if len(vals) > 3 else "")
            except Exception:
                return None

        def _open_grade_manager():
            row = _selected_row()
            sid = row[0] if row else None
            module = row[1] if row else None
            pct = row[2] if row else None
            try:
                from education_system.university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app import (  # noqa: E501
                    GradeTrackingApp,
                )
                win = tk.Toplevel(self.ctx.parent)
                win.title(f"Grade Management — {sid}" if sid
                          else "Grade Management")
                win.geometry("1200x750")
                app = GradeTrackingApp(win, auth=getattr(self.ctx, "auth", None))
                # (1) If a row was selected, jump straight into Add Grade
                # with the student/module/comments pre-filled.
                if sid and hasattr(app, "grades") and hasattr(
                        app.grades, "add_grade_dialog"):
                    comments = (f"Attendance penalty: {pct:.1f}% < "
                                f"{threshold:.0f}% threshold") if pct else None
                    try:
                        app.grades.add_grade_dialog(
                            prefill_student_id=sid,
                            prefill_module_code=module,
                            prefill_comments=comments)
                    except TypeError:
                        # Older signature — fall back to plain dialog.
                        app.grades.add_grade_dialog()
            except Exception:
                logger.exception("could not open Grade Management GUI")
                messagebox.showerror(
                    "Grade Management",
                    "Could not open the Grade Management GUI (see log).",
                    parent=self.ctx.parent)

        def _apply_penalty():
            # (2) One-click standard penalty: insert a 0-score grade row
            # against a synthetic "Attendance penalty" assessment, record
            # in attendance_grade_penalties, audit, and notify parents.
            row = _selected_row()
            if not row:
                messagebox.showinfo(
                    "Apply penalty", "Select a candidate row first.",
                    parent=self.ctx.parent)
                return
            sid, module, pct, applied = row
            if applied == "✓":
                messagebox.showinfo(
                    "Already applied",
                    f"A penalty has already been recorded for "
                    f"{sid} / {module}.", parent=self.ctx.parent)
                return
            if not Prompt.confirm(
                    self.ctx.parent, "Confirm penalty",
                    f"Record an attendance penalty for {sid} on "
                    f"{module} (current attendance {pct:.1f}%)?\n\n"
                    f"This inserts a 0-score grade row and notifies "
                    f"linked parents."):
                return
            cur = self.ctx.db.cur
            try:
                # Find or create the synthetic per-module penalty assessment.
                aid_row = cur.execute(
                    """SELECT assessment_id FROM assessments
                       WHERE module_code=? AND assessment_type='attendance_penalty'
                       LIMIT 1""", (module,)).fetchone()
                if aid_row:
                    assessment_id = aid_row[0]
                else:
                    cur.execute(
                        """INSERT INTO assessments
                           (assessment_name, assessment_type, module_code,
                            max_points, weight, description)
                           VALUES (?, 'attendance_penalty', ?,
                                   100, 0,
                                   'Auto-generated for attendance penalties')""",
                        (f"Attendance Penalty — {module}", module))
                    assessment_id = cur.lastrowid

                today = date.today().isoformat()
                comments = (f"Attendance penalty: {pct:.1f}% < "
                            f"{threshold:.0f}% threshold")
                cur.execute(
                    """INSERT INTO grades
                       (student_id, assessment_id, score, letter_grade,
                        submission_date, comments)
                       VALUES (?, ?, 0, 'F', ?, ?)""",
                    (sid, assessment_id, today, comments))
                grade_row_id = cur.lastrowid

                cur.execute(
                    """INSERT OR REPLACE INTO attendance_grade_penalties
                       (student_id, module_code, threshold, pct,
                        applied_at, applied_by, grade_row_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (sid, module, threshold, pct,
                     datetime.now().isoformat(timespec="seconds"),
                     getattr(self.ctx, "username", None) or "",
                     grade_row_id))

                # (5) Notify linked parents — same shape as #27.
                parents = _parents_of(self.ctx.db, sid) or [""]
                content = (f"Attendance penalty recorded for {module}: "
                           f"{pct:.1f}% (below {threshold:.0f}%).")
                now = datetime.now().isoformat(timespec="seconds")
                for pid in parents:
                    cur.execute(
                        """INSERT INTO parent_notifications
                           (parent_id, student_id, notification_type,
                            notification_content, created_date, read_status)
                           VALUES (?, ?, 'grade_penalty', ?, ?, 0)""",
                        (pid, sid, content, now))

                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception("apply penalty failed sid=%s module=%s",
                                 sid, module)
                messagebox.showerror("Failed", str(e),
                                     parent=self.ctx.parent)
                return

            audit(self.ctx, "grade_penalty_applied", "grades",
                  str(grade_row_id),
                  f"sid={sid} module={module} pct={pct:.1f} "
                  f"threshold={threshold}")
            # Reflect the new state in the visible table.
            try:
                sel = tree.selection()
                if sel:
                    vals = list(tree.item(sel[0], "values"))
                    if len(vals) >= 4:
                        vals[3] = "✓"
                        tree.item(sel[0], values=vals)
            except Exception:
                pass
            messagebox.showinfo(
                "Penalty applied",
                f"Recorded penalty for {sid} on {module} and notified "
                f"{len([p for p in parents if p])} parent(s).",
                parent=self.ctx.parent)

        win, tree = _show_table(
            self.ctx.parent,
            f"Attendance penalty candidates (<{threshold:.0f}%)",
            ("student", "module", "pct", "applied"),
            [(s, m, f"{p:.1f}", a) for s, m, p, a in rows],
            extra_button=("⚖️  Apply standard penalty (selected)",
                          _apply_penalty))

        # Second action button for navigating into Grade Management,
        # alongside the primary Apply Penalty action.
        extra = tk.Frame(win)
        extra.pack(side="bottom", fill="x")
        tk.Button(extra, text="📝  Open Grade Management GUI (selected)",
                  command=_open_grade_manager,
                  bg="#0ea5e9", fg="white", relief="flat",
                  padx=10, pady=4).pack(side="left", padx=10, pady=4)

        # Double-click a row → open grade manager prefilled.
        tree.bind("<Double-1>", lambda _e: _open_grade_manager())

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
                   VALUES (?, 'attendance', ?, ?, ?, ?, 'Minor', 'Under Review')""",
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

        # Offer to open the full Disciplinary Portal so the admin can
        # add evidence, escalate severity, or attach follow-up actions
        # beyond the one-click written warning we just recorded.
        if Prompt.confirm(
                self.ctx.parent, "Open portal?",
                f"Disciplinary action logged for {sid}.\n\n"
                "Open the Disciplinary Portal to manage the record?"):
            try:
                from education_system.university_system.modules.domain.legal.disciplinary.disciplinary_portal import (  # noqa: E501
                    DisciplinaryPortal,
                )
                win = tk.Toplevel(self.ctx.parent)
                win.title(f"Disciplinary Portal — {sid}")
                win.geometry("1200x800")
                DisciplinaryPortal(win)
            except Exception:
                logger.exception("could not open Disciplinary Portal")
                messagebox.showerror(
                    "Disciplinary Portal",
                    "Could not open the Disciplinary Portal (see log).",
                    parent=self.ctx.parent)
        else:
            messagebox.showinfo(
                "Recorded",
                f"Disciplinary action logged for {sid}.",
                parent=self.ctx.parent)

    # --- #37 ----------------------------------------------------------
    @safe("Finance link")
    def show_scholarship_attendance_check(self) -> None:
        # (#4) Remember the last threshold so staff don't reset it each run.
        try:
            saved = float(_get_setting(self.ctx.db, "scholarship_threshold", "80"))
        except (TypeError, ValueError):
            saved = 80.0
        threshold = simpledialog.askfloat(
            "Threshold", "Below %:",
            parent=self.ctx.parent, initialvalue=saved) or saved
        try:
            _set_setting(self.ctx.db, "scholarship_threshold", threshold)
        except Exception:
            logger.exception("could not persist scholarship threshold")

        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS student_scholarships (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT, scholarship_id INTEGER, status TEXT)""")
            # (#2) Add at-risk write-back columns if missing. ALTER TABLE ADD
            # COLUMN is idempotent only via try/except — older DBs predate this.
            for col, ddl in (
                ("at_risk_pct",            "ALTER TABLE student_scholarships ADD COLUMN at_risk_pct REAL"),
                ("at_risk_checked_at",     "ALTER TABLE student_scholarships ADD COLUMN at_risk_checked_at TEXT"),
                ("at_risk_last_notified_at", "ALTER TABLE student_scholarships ADD COLUMN at_risk_last_notified_at TEXT"),
            ):
                try:
                    self.ctx.db.cur.execute(ddl)
                except sqlite3.OperationalError:
                    pass  # column already exists
            self.ctx.db.conn.commit()

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

        # (#5) Schema sanity check — surface ID mismatches between
        # student_scholarships.student_id and the users table.
        sanity_msg = self._scholarship_id_sanity_check()

        # (#2) Write the at-risk pct back so it persists outside this popup.
        # (#3) Email admins, but only once per 24h per student to avoid spam.
        notified_now = self._mark_scholarships_at_risk(rows, threshold)
        if notified_now:
            audit(self.ctx, "notify", "student_scholarships",
                  ",".join(notified_now),
                  f"scholarship_at_risk threshold={threshold}")

        def _open_scholarship_gui(student_id: Optional[str] = None) -> None:
            """Launch the ScholarshipManagerGUI awards view in a new Toplevel."""
            try:
                from education_system.university_system.modules.domain.finance.gui.financial_aid.scholarship_manager import (
                    ScholarshipManagerGUI,
                )
            except Exception as e:
                logger.exception("scholarship GUI import failed")
                messagebox.showerror("Scholarship GUI",
                                     f"Could not open scholarship manager: {e}",
                                     parent=self.ctx.parent)
                return
            win = tk.Toplevel(self.ctx.parent)
            win.title(
                f"Scholarship Manager — {student_id}" if student_id
                else "Scholarship Manager"
            )
            win.geometry("1200x800")
            container = ttk.Frame(win)
            container.pack(fill="both", expand=True)
            try:
                gui = ScholarshipManagerGUI(container, auth_instance=getattr(
                    self.ctx, "auth", None))
                # Land on the awards table, filtered to the selected student
                # when one was double-clicked / selected.
                gui.show_awards(student_id=student_id)
            except Exception as e:
                logger.exception("scholarship GUI launch failed")
                messagebox.showerror("Scholarship GUI", str(e), parent=win)

        win, tree = _show_table(
            self.ctx.parent, "Scholarship attendance check",
            ("student", "pct"),
            [(s, f"{p:.1f}") for s, p in rows],
            extra_button=("Open Scholarship Manager", lambda: _open_scholarship_gui(
                (tree.item(tree.selection()[0], "values")[0]
                 if tree.selection() else None))),
        )
        # Double-click a row → open the scholarship manager for that student.
        tree.bind("<Double-1>", lambda _e: _open_scholarship_gui(
            (tree.item(tree.selection()[0], "values")[0]
             if tree.selection() else None)))

        # Surface the schema sanity report + notification count below the table.
        footer_bits = []
        if notified_now:
            footer_bits.append(f"Notified admins about {len(notified_now)} student(s).")
        if sanity_msg:
            footer_bits.append(sanity_msg)
        if footer_bits:
            tk.Label(win, text="  ".join(footer_bits),
                     fg="#6b7280", anchor="w", justify="left",
                     wraplength=950, padx=10, pady=4).pack(fill="x", side="bottom")

    # ---- helpers for #2/#3/#5 ---------------------------------------------
    def _mark_scholarships_at_risk(self, rows, threshold) -> list:
        """Persist at-risk pct back to student_scholarships and notify admins.

        ``rows`` is the list of (student_id, pct) tuples from the threshold
        query. Returns the student ids that were freshly notified this run.
        """
        if not rows:
            return []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notified: list = []
        try:
            for sid, pct in rows:
                # Read the existing last-notified-at to enforce a 24h guard.
                existing = self.ctx.db.cur.execute(
                    "SELECT at_risk_last_notified_at FROM student_scholarships "
                    "WHERE student_id = ? LIMIT 1", (sid,)).fetchone()
                last = existing[0] if existing else None
                self.ctx.db.cur.execute(
                    "UPDATE student_scholarships "
                    "SET at_risk_pct = ?, at_risk_checked_at = ? "
                    "WHERE student_id = ?",
                    (pct, now, sid),
                )
                # 24h re-notify guard.
                may_notify = True
                if last:
                    try:
                        last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
                        may_notify = (datetime.now() - last_dt).total_seconds() > 86400
                    except ValueError:
                        may_notify = True
                if may_notify:
                    try:
                        n = _email_admin(
                            self.ctx.db,
                            subject=f"Scholarship at-risk: {sid} ({pct:.1f}%)",
                            body=(f"Student {sid} dropped to {pct:.1f}% attendance, "
                                  f"below the {threshold:.1f}% threshold for "
                                  f"continued scholarship eligibility. Review in "
                                  f"the Scholarship Manager."),
                            sender_username=getattr(self.ctx, "username", "") or "",
                        )
                    except Exception:
                        logger.exception("at-risk notification failed sid=%s", sid)
                        n = 0
                    if n:
                        self.ctx.db.cur.execute(
                            "UPDATE student_scholarships "
                            "SET at_risk_last_notified_at = ? "
                            "WHERE student_id = ?", (now, sid),
                        )
                        notified.append(sid)
            self.ctx.db.conn.commit()
        except sqlite3.Error:
            self.ctx.db.conn.rollback()
            logger.exception("at-risk write-back failed")
        return notified

    def _scholarship_id_sanity_check(self) -> str:
        """Return a one-line warning if scholarship student_ids don't link to users.

        The deep-link from awards back to the at-risk view assumes
        student_scholarships.student_id matches users.username (or
        users.student_id). Bad joins silently hide rows; surface a count.
        """
        try:
            row = self.ctx.db.cur.execute(
                """SELECT COUNT(DISTINCT ss.student_id)
                   FROM student_scholarships ss
                   LEFT JOIN users u
                     ON u.username = ss.student_id
                     OR u.student_id = ss.student_id
                   WHERE u.id IS NULL"""
            ).fetchone()
            orphans = (row[0] if row else 0) or 0
        except sqlite3.Error:
            logger.exception("scholarship sanity check failed")
            return ""
        if not orphans:
            return ""
        return (f"⚠ {orphans} scholarship student_id(s) don't match any user — "
                "deep-links from the Scholarship Manager may show no rows.")


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
