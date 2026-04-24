"""
Admin features for the Absence Tracker.

Fifty admin utilities, each wrapped with logging and error handling. Every
feature is self-contained: it takes an :class:`AdminContext` (carrying the
DB handle, parent Tk window, and current user) and either opens a dialog or
returns a result.

Logging is configured once at module import. A rolling log lives under the
main LOG_DIR so admin actions are traceable across sessions.
"""

from __future__ import annotations

import csv
import functools
import io
import json
import logging
import os
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Iterable, Optional

try:
    from education_system.university_system.modules.shared.constants.paths import LOG_DIR
    _LOG_PATH = Path(LOG_DIR) / "absence_tracker.log"
except Exception:
    _LOG_PATH = Path.home() / ".absence_tracker.log"

logger = logging.getLogger("absence_tracker.admin")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        h = RotatingFileHandler(_LOG_PATH, maxBytes=2_000_000, backupCount=3)
        h.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        ))
        logger.addHandler(h)
    except Exception:
        logger.addHandler(logging.StreamHandler())


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------
@dataclass
class AdminContext:
    """Lightweight bag passed into every admin feature."""
    db: Any                       # absence_tracker.Database instance
    parent: tk.Misc               # root / parent window
    user: dict                    # authenticated user dict


def ensure_support_tables(db) -> None:
    """Create all support tables used by the admin features if missing."""
    cur = db.cur
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS abs_tracker_audit (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT DEFAULT CURRENT_TIMESTAMP,
            user_id     INTEGER,
            username    TEXT,
            action      TEXT,
            target      TEXT,
            target_id   TEXT,
            details     TEXT
        );

        CREATE TABLE IF NOT EXISTS abs_tracker_trash (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            deleted_at     TEXT DEFAULT CURRENT_TIMESTAMP,
            deleted_by     TEXT,
            original_table TEXT,
            original_id    INTEGER,
            payload        TEXT
        );

        CREATE TABLE IF NOT EXISTS abs_tracker_settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS abs_tracker_module_policy (
            module_code      TEXT PRIMARY KEY,
            min_percent      REAL,
            late_as_absent   INTEGER,
            grace_minutes    INTEGER,
            notes            TEXT
        );

        CREATE TABLE IF NOT EXISTS abs_tracker_statuses (
            code       TEXT PRIMARY KEY,
            label      TEXT,
            counts_as  TEXT
        );

        CREATE TABLE IF NOT EXISTS abs_tracker_auto_excuse_rules (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            status     TEXT DEFAULT 'excused',
            enabled    INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS abs_tracker_request_attachments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id  INTEGER,
            file_path   TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS abs_tracker_request_comments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            author     TEXT,
            body       TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS abs_tracker_request_templates (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT UNIQUE,
            body    TEXT
        );

        CREATE TABLE IF NOT EXISTS abs_tracker_delegations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user   INTEGER,
            to_user     INTEGER,
            active_from TEXT,
            active_to   TEXT
        );

        CREATE TABLE IF NOT EXISTS abs_tracker_scheduled_reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT,
            frequency   TEXT,
            recipients  TEXT,
            report_type TEXT,
            last_run    TEXT,
            enabled     INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS abs_tracker_retention (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            policy     TEXT,
            years      INTEGER,
            applied_at TEXT
        );
    """)
    # seed default statuses
    cur.executemany(
        "INSERT OR IGNORE INTO abs_tracker_statuses (code, label, counts_as) VALUES (?,?,?)",
        [
            ("present", "Present", "present"),
            ("absent",  "Absent",  "absent"),
            ("late",    "Late",    "late"),
            ("excused", "Excused", "excused"),
        ],
    )
    db.conn.commit()


def audit(ctx: AdminContext, action: str, target: str = "", target_id: str = "",
          details: str = "") -> None:
    """Write a row to the admin audit table. Non-fatal on failure."""
    try:
        ctx.db.cur.execute(
            """INSERT INTO abs_tracker_audit
               (user_id, username, action, target, target_id, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ctx.user.get("id"), ctx.user.get("username"),
             action, target, str(target_id), details),
        )
        ctx.db.conn.commit()
    except Exception:
        logger.exception("audit write failed for action=%s", action)


def safe(title: str = "Error") -> Callable:
    """Decorator: logs + shows a friendly error dialog on any exception."""
    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapped(ctx: AdminContext, *args, **kwargs):
            try:
                logger.info("▶ %s user=%s", fn.__name__, ctx.user.get("username"))
                out = fn(ctx, *args, **kwargs)
                logger.info("✓ %s", fn.__name__)
                return out
            except Exception as e:
                logger.exception("✗ %s failed", fn.__name__)
                try:
                    messagebox.showerror(
                        title, f"{fn.__name__} failed:\n{e}", parent=ctx.parent
                    )
                except Exception:
                    pass
        return wrapped
    return deco


# ---------------------------------------------------------------------------
# Shared dialog helpers
# ---------------------------------------------------------------------------
def _pick_student(ctx: AdminContext, prompt="Pick a student") -> Optional[str]:
    rows = ctx.db.get_users("student")
    if not rows:
        messagebox.showinfo("No students", "No students in the database.",
                            parent=ctx.parent)
        return None
    options = {f"{r[3] or r[1]} ({r[1]})": r[0] for r in rows}
    pick = _combo_dialog(ctx.parent, prompt, "Student:", list(options.keys()))
    return options.get(pick) if pick else None


def _pick_module(ctx: AdminContext, prompt="Pick a module") -> Optional[str]:
    rows = ctx.db.get_courses()
    if not rows:
        messagebox.showinfo("No modules", "No modules in the database.",
                            parent=ctx.parent)
        return None
    options = {f"{r[1]} - {r[2]}": r[0] for r in rows}
    pick = _combo_dialog(ctx.parent, prompt, "Module:", list(options.keys()))
    return options.get(pick) if pick else None


def pick_date(parent, title="Pick a date", initial: Optional[date] = None) -> Optional[str]:
    """Open a modal dialog with year/month/day Comboboxes. Returns 'YYYY-MM-DD' or None."""
    import calendar as _cal
    today = initial or date.today()
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent)
    dlg.grab_set()
    dlg.geometry("360x180")
    tk.Label(dlg, text=title, font=("Arial", 11, "bold")).pack(pady=10)

    row = tk.Frame(dlg)
    row.pack(pady=6)

    years = [str(y) for y in range(today.year - 2, today.year + 4)]
    months = [f"{m:02d}" for m in range(1, 13)]

    y_var = tk.StringVar(value=str(today.year))
    m_var = tk.StringVar(value=f"{today.month:02d}")
    d_var = tk.StringVar(value=f"{today.day:02d}")

    def days_for(y: str, m: str) -> list[str]:
        try:
            n = _cal.monthrange(int(y), int(m))[1]
        except Exception:
            n = 31
        return [f"{d:02d}" for d in range(1, n + 1)]

    tk.Label(row, text="Year").grid(row=0, column=0, padx=4)
    tk.Label(row, text="Month").grid(row=0, column=1, padx=4)
    tk.Label(row, text="Day").grid(row=0, column=2, padx=4)

    y_cb = ttk.Combobox(row, textvariable=y_var, values=years, width=6, state="readonly")
    m_cb = ttk.Combobox(row, textvariable=m_var, values=months, width=5, state="readonly")
    d_cb = ttk.Combobox(row, textvariable=d_var, values=days_for(y_var.get(), m_var.get()),
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

    def cancel():
        dlg.destroy()

    btns = tk.Frame(dlg); btns.pack(pady=12)
    tk.Button(btns, text="OK", command=ok, bg="#2563eb", fg="white",
              relief="flat", padx=18, pady=4).pack(side="left", padx=6)
    tk.Button(btns, text="Cancel", command=cancel, bg="#6b7280", fg="white",
              relief="flat", padx=18, pady=4).pack(side="left", padx=6)
    dlg.wait_window()
    return result["v"]


def pick_date_range(parent, title="Pick a date range") -> Optional[tuple[str, str]]:
    """Open two sequential date pickers. Returns (start, end) or None."""
    start = pick_date(parent, f"{title} — start date")
    if not start:
        return None
    try:
        init = datetime.strptime(start, "%Y-%m-%d").date()
    except Exception:
        init = None
    end = pick_date(parent, f"{title} — end date", initial=init)
    if not end:
        return None
    if end < start:
        start, end = end, start
    return start, end


def _combo_dialog(parent, title, label, values) -> Optional[str]:
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent)
    dlg.grab_set()
    dlg.geometry("520x140")
    tk.Label(dlg, text=label).pack(pady=8)
    var = tk.StringVar()
    cb = ttk.Combobox(dlg, textvariable=var, values=values, state="readonly", width=60)
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
              fg="white", relief="flat", padx=10, pady=4).pack(side="right", padx=10)
    return win, tree


def _export_rows_to_csv(rows: Iterable, headers: Iterable[str], parent) -> Optional[str]:
    path = filedialog.asksaveasfilename(
        parent=parent, defaultextension=".csv",
        filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
    )
    if not path:
        return None
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(list(headers))
        w.writerows(rows)
    return path


def _get_setting(db, key, default=None):
    r = db.cur.execute("SELECT value FROM abs_tracker_settings WHERE key=?", (key,)).fetchone()
    return r[0] if r else default


def _set_setting(db, key, value):
    db.cur.execute(
        "INSERT OR REPLACE INTO abs_tracker_settings (key, value) VALUES (?, ?)",
        (key, str(value)),
    )
    db.conn.commit()


# ===========================================================================
# 1–7  Attendance data management
# ===========================================================================

@safe("Bulk import")
def feat_01_bulk_import(ctx: AdminContext):
    """Import attendance rows from a CSV: student_id,module_code,date,status[,reason]."""
    path = filedialog.askopenfilename(
        parent=ctx.parent, filetypes=[("CSV", "*.csv"), ("All", "*.*")])
    if not path:
        return
    ok = 0
    bad = 0
    with open(path, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                ctx.db.record_absence(
                    row["student_id"].strip(),
                    row["module_code"].strip(),
                    row["date"].strip(),
                    row["status"].strip(),
                    (row.get("reason") or "").strip(),
                )
                ok += 1
            except Exception as e:
                logger.warning("import row %s failed: %s", row, e)
                bad += 1
    audit(ctx, "bulk_import", "attendance", "", f"ok={ok} bad={bad} file={path}")
    messagebox.showinfo("Import complete",
                        f"Imported {ok} rows. {bad} rejected.", parent=ctx.parent)


@safe("Bulk export")
def feat_02_bulk_export(ctx: AdminContext):
    """Export all attendance rows (with student and module names) to CSV."""
    rows = ctx.db.get_absences()
    headers = ("id", "student", "module_code", "module_name",
               "date", "status", "reason")
    path = _export_rows_to_csv(rows, headers, ctx.parent)
    if path:
        audit(ctx, "bulk_export", "attendance", "", f"rows={len(rows)} file={path}")
        messagebox.showinfo("Exported", f"Wrote {len(rows)} rows to:\n{path}",
                            parent=ctx.parent)


@safe("Edit record")
def feat_03_edit_record(ctx: AdminContext):
    """Edit an existing attendance row in place (status/reason)."""
    rid = simpledialog.askinteger("Edit", "Attendance row id:", parent=ctx.parent)
    if rid is None:
        return
    old = ctx.db.cur.execute(
        "SELECT status, reason FROM attendance WHERE id=?", (rid,)).fetchone()
    if not old:
        messagebox.showerror("Not found", f"No row {rid}", parent=ctx.parent)
        return
    new_status = simpledialog.askstring("Status",
                                        f"New status (was {old[0]}):",
                                        parent=ctx.parent) or old[0]
    new_reason = simpledialog.askstring("Reason",
                                        f"New reason (was {old[1] or ''}):",
                                        parent=ctx.parent) or old[1]
    ctx.db.cur.execute("UPDATE attendance SET status=?, reason=? WHERE id=?",
                       (new_status, new_reason, rid))
    ctx.db.conn.commit()
    audit(ctx, "edit_record", "attendance", rid,
          f"{old[0]}→{new_status}")
    messagebox.showinfo("Saved", "Record updated.", parent=ctx.parent)


@safe("Undo delete")
def feat_04_undo_delete(ctx: AdminContext):
    """Restore soft-deleted attendance rows from the 24-hour trash."""
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    rows = ctx.db.cur.execute(
        """SELECT id, deleted_at, deleted_by, original_table, payload
           FROM abs_tracker_trash WHERE deleted_at >= ?
           ORDER BY deleted_at DESC""", (cutoff,)).fetchall()
    if not rows:
        messagebox.showinfo("Trash empty", "Nothing deleted in the last 24h.",
                            parent=ctx.parent)
        return

    def restore_selected():
        sel = tree.selection()
        if not sel:
            return
        for item in sel:
            v = tree.item(item)["values"]
            p = json.loads(v[4])
            ctx.db.cur.execute(
                """INSERT INTO attendance (id, student_id, module_code, date, status, reason)
                   VALUES (?,?,?,?,?,?)""",
                (p["id"], p["student_id"], p["module_code"], p["date"],
                 p["status"], p["reason"]))
            ctx.db.cur.execute("DELETE FROM abs_tracker_trash WHERE id=?", (v[0],))
        ctx.db.conn.commit()
        audit(ctx, "undo_delete", "attendance", "", f"rows={len(sel)}")
        messagebox.showinfo("Restored", f"Restored {len(sel)} row(s).", parent=win)
        win.destroy()

    win, tree = _show_table(ctx.parent, "Trash (24h)",
                            ("id", "deleted_at", "deleted_by", "table", "payload"),
                            rows, extra_button=("Restore selected", restore_selected))


@safe("Merge duplicates")
def feat_05_merge_duplicates(ctx: AdminContext):
    """Find and collapse duplicate (student, module, date) attendance rows."""
    dups = ctx.db.cur.execute(
        """SELECT student_id, module_code, date, COUNT(*) c, MIN(id), MAX(id)
           FROM attendance
           GROUP BY student_id, module_code, date HAVING c > 1""").fetchall()
    if not dups:
        messagebox.showinfo("No duplicates", "No duplicate rows found.", parent=ctx.parent)
        return
    removed = 0
    for _sid, _mod, _d, _c, keep_id, _max in dups:
        cur = ctx.db.cur.execute(
            """DELETE FROM attendance
               WHERE student_id=? AND module_code=? AND date=? AND id<>?""",
            (_sid, _mod, _d, keep_id))
        removed += cur.rowcount
    ctx.db.conn.commit()
    audit(ctx, "merge_duplicates", "attendance", "", f"removed={removed}")
    messagebox.showinfo("Merged",
                        f"Removed {removed} duplicate row(s), kept earliest per day.",
                        parent=ctx.parent)


@safe("Audit log")
def feat_06_correction_audit(ctx: AdminContext):
    """Show the admin correction/audit log."""
    rows = ctx.db.cur.execute(
        """SELECT ts, username, action, target, target_id, details
           FROM abs_tracker_audit ORDER BY ts DESC LIMIT 500""").fetchall()
    _show_table(ctx.parent, "Audit log (last 500)",
                ("when", "user", "action", "target", "target_id", "details"),
                rows, widths=[150, 120, 140, 100, 100, 380])


@safe("Lock past dates")
def feat_07_lock_past_dates(ctx: AdminContext):
    """Lock edits to attendance rows older than N days via a setting + trigger."""
    days = simpledialog.askinteger(
        "Lock past dates",
        "Lock edits to records older than how many days?",
        parent=ctx.parent, minvalue=0, maxvalue=3650)
    if days is None:
        return
    _set_setting(ctx.db, "lock_days", days)
    # Install/refresh a SQLite trigger enforcing the lock.
    ctx.db.cur.executescript(f"""
        DROP TRIGGER IF EXISTS abs_lock_update;
        CREATE TRIGGER abs_lock_update
        BEFORE UPDATE ON attendance
        FOR EACH ROW
        WHEN julianday('now') - julianday(OLD.date) > {int(days)}
        BEGIN
          SELECT RAISE(ABORT, 'Attendance row older than lock window');
        END;
    """)
    ctx.db.conn.commit()
    audit(ctx, "lock_past_dates", "settings", "lock_days", str(days))
    messagebox.showinfo("Locked",
                        f"Records older than {days} day(s) are now read-only.",
                        parent=ctx.parent)


# ===========================================================================
# 8–13  Absence request workflow
# ===========================================================================

@safe("Bulk approve")
def feat_08_bulk_approve_reject(ctx: AdminContext):
    """Approve or reject all pending requests matching a filter."""
    mod = _pick_module(ctx, "Limit to module (Cancel = all modules)") or None
    action = _combo_dialog(ctx.parent, "Decide", "Action for all pending:",
                           ["approved", "rejected"])
    if not action:
        return
    q = "SELECT id, student_id, module_code, date, reason FROM absence_requests WHERE status='pending'"
    p = []
    if mod:
        q += " AND module_code=?"
        p.append(mod)
    pending = ctx.db.cur.execute(q, p).fetchall()
    for rid, sid, mc, d, reason in pending:
        ctx.db.update_request(rid, action)
        if action == "approved":
            ctx.db.record_absence(sid, mc, d, "excused",
                                  f"[Bulk-approved] {reason}")
    audit(ctx, "bulk_request_decide", "absence_requests", "",
          f"action={action} n={len(pending)}")
    messagebox.showinfo("Done", f"{action.title()} {len(pending)} request(s).",
                        parent=ctx.parent)


@safe("Attach document")
def feat_09_request_attachment(ctx: AdminContext):
    """Attach a supporting document (e.g. doctor's note) to a request."""
    rid = simpledialog.askinteger("Attachment", "Request id:", parent=ctx.parent)
    if rid is None:
        return
    path = filedialog.askopenfilename(parent=ctx.parent)
    if not path:
        return
    ctx.db.cur.execute(
        "INSERT INTO abs_tracker_request_attachments (request_id, file_path) VALUES (?,?)",
        (rid, path))
    ctx.db.conn.commit()
    audit(ctx, "request_attach", "absence_requests", rid, path)
    messagebox.showinfo("Attached", f"Attached:\n{path}", parent=ctx.parent)


@safe("Expire pending")
def feat_10_expire_pending(ctx: AdminContext):
    """Auto-expire pending absence requests older than N days."""
    days = simpledialog.askinteger("Expire", "Expire pending older than (days)?",
                                   parent=ctx.parent, minvalue=1, maxvalue=365)
    if days is None:
        return
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cur = ctx.db.cur.execute(
        """UPDATE absence_requests SET status='rejected'
           WHERE status='pending' AND submitted_at < ?""", (cutoff,))
    ctx.db.conn.commit()
    audit(ctx, "expire_pending", "absence_requests", "", f"cutoff={cutoff} n={cur.rowcount}")
    messagebox.showinfo("Expired", f"Rejected {cur.rowcount} stale request(s).",
                        parent=ctx.parent)


@safe("Delegate approval")
def feat_11_delegate_approval(ctx: AdminContext):
    """Delegate approval authority from one staff user to another."""
    staff = ctx.db.get_users("staff") + ctx.db.get_users("instructor")
    mapping = {f"{r[3] or r[1]} ({r[1]})": r[0] for r in staff}
    if len(mapping) < 2:
        messagebox.showinfo("Need ≥2 staff", "Not enough staff/instructor users.",
                            parent=ctx.parent)
        return
    src = _combo_dialog(ctx.parent, "Delegate from", "From:", list(mapping.keys()))
    dst = _combo_dialog(ctx.parent, "Delegate to", "To:", list(mapping.keys()))
    if not (src and dst and src != dst):
        return
    start = simpledialog.askstring("Start", "Active from (YYYY-MM-DD):",
                                   parent=ctx.parent) or date.today().isoformat()
    end = simpledialog.askstring("End", "Active to (YYYY-MM-DD):",
                                 parent=ctx.parent) or (
        date.today() + timedelta(days=14)).isoformat()
    ctx.db.cur.execute(
        """INSERT INTO abs_tracker_delegations (from_user, to_user, active_from, active_to)
           VALUES (?,?,?,?)""",
        (mapping[src], mapping[dst], start, end))
    ctx.db.conn.commit()
    audit(ctx, "delegate", "abs_tracker_delegations", "",
          f"{mapping[src]}→{mapping[dst]} {start}..{end}")
    messagebox.showinfo("Delegated",
                        f"{src} → {dst} from {start} to {end}", parent=ctx.parent)


@safe("Request comments")
def feat_12_request_comment_thread(ctx: AdminContext):
    """View/append a comment thread on an absence request."""
    rid = simpledialog.askinteger("Comments", "Request id:", parent=ctx.parent)
    if rid is None:
        return
    rows = ctx.db.cur.execute(
        """SELECT created_at, author, body FROM abs_tracker_request_comments
           WHERE request_id=? ORDER BY created_at""", (rid,)).fetchall()
    win = tk.Toplevel(ctx.parent)
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
        ctx.db.cur.execute(
            """INSERT INTO abs_tracker_request_comments (request_id, author, body)
               VALUES (?,?,?)""",
            (rid, ctx.user.get("username", "?"), body))
        ctx.db.conn.commit()
        audit(ctx, "request_comment", "absence_requests", rid, body[:120])
        txt.config(state="normal")
        txt.insert("end",
                   f"[{datetime.now().isoformat(timespec='seconds')}] "
                   f"{ctx.user.get('username','?')}:\n{body}\n\n")
        txt.config(state="disabled")
        entry.delete("1.0", "end")

    tk.Button(win, text="Post", command=post, bg="#2563eb", fg="white",
              relief="flat", padx=12, pady=4).pack(pady=8)


@safe("Request templates")
def feat_13_request_templates(ctx: AdminContext):
    """Manage predefined request templates (medical, bereavement, etc.)."""
    win = tk.Toplevel(ctx.parent)
    win.title("Request templates")
    win.geometry("560x420")

    tree = ttk.Treeview(win, columns=("id", "name"), show="headings")
    for c, w in zip(("id", "name"), (60, 400)):
        tree.heading(c, text=c)
        tree.column(c, width=w)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    def refresh():
        for i in tree.get_children():
            tree.delete(i)
        for row in ctx.db.cur.execute(
                "SELECT id, name FROM abs_tracker_request_templates ORDER BY name"):
            tree.insert("", "end", values=row)

    def add():
        name = simpledialog.askstring("Template name", "Name:", parent=win)
        if not name:
            return
        body = simpledialog.askstring("Body", "Template body:", parent=win) or ""
        ctx.db.cur.execute(
            "INSERT OR REPLACE INTO abs_tracker_request_templates (name, body) VALUES (?,?)",
            (name, body))
        ctx.db.conn.commit()
        audit(ctx, "template_add", "abs_tracker_request_templates", "", name)
        refresh()

    def delete():
        sel = tree.selection()
        if not sel:
            return
        tid = tree.item(sel[0])["values"][0]
        ctx.db.cur.execute(
            "DELETE FROM abs_tracker_request_templates WHERE id=?", (tid,))
        ctx.db.conn.commit()
        audit(ctx, "template_delete", "abs_tracker_request_templates", tid, "")
        refresh()

    bar = tk.Frame(win)
    bar.pack(fill="x", pady=5)
    tk.Button(bar, text="➕ Add", command=add, bg="#16a34a", fg="white",
              relief="flat", padx=10).pack(side="left", padx=6)
    tk.Button(bar, text="🗑 Delete", command=delete, bg="#dc2626", fg="white",
              relief="flat", padx=10).pack(side="left", padx=6)
    refresh()


# ===========================================================================
# 14–18  Policies & thresholds
# ===========================================================================

@safe("Module policy")
def feat_14_module_policy(ctx: AdminContext):
    """Set per-module attendance policy (minimum %, late-as-absent, grace)."""
    mc = _pick_module(ctx, "Policy for which module?")
    if not mc:
        return
    row = ctx.db.cur.execute(
        "SELECT min_percent, late_as_absent, grace_minutes, notes FROM abs_tracker_module_policy WHERE module_code=?",
        (mc,)).fetchone()
    cur_pct, cur_lta, cur_grace, cur_notes = row or (80.0, 0, 5, "")
    pct = simpledialog.askfloat("Min %", f"Minimum attendance % (current {cur_pct})",
                                parent=ctx.parent, minvalue=0, maxvalue=100)
    lta = simpledialog.askinteger("Late=Absent",
                                  f"1 to count late as absent (current {cur_lta}):",
                                  parent=ctx.parent, minvalue=0, maxvalue=1)
    grace = simpledialog.askinteger("Grace",
                                    f"Grace minutes before 'late' (current {cur_grace}):",
                                    parent=ctx.parent, minvalue=0, maxvalue=120)
    notes = simpledialog.askstring("Notes", "Notes:", parent=ctx.parent) or cur_notes
    ctx.db.cur.execute(
        """INSERT OR REPLACE INTO abs_tracker_module_policy
           (module_code, min_percent, late_as_absent, grace_minutes, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (mc, pct if pct is not None else cur_pct,
         lta if lta is not None else cur_lta,
         grace if grace is not None else cur_grace, notes))
    ctx.db.conn.commit()
    audit(ctx, "module_policy", "abs_tracker_module_policy", mc,
          f"pct={pct} lta={lta} grace={grace}")
    messagebox.showinfo("Saved", f"Policy for {mc} saved.", parent=ctx.parent)


@safe("Default policy")
def feat_15_default_policy(ctx: AdminContext):
    """Set university-wide default attendance policy."""
    pct = simpledialog.askfloat(
        "Default min %",
        f"Default attendance min % (now {_get_setting(ctx.db,'default_min_pct', '80')}):",
        parent=ctx.parent, minvalue=0, maxvalue=100)
    if pct is None:
        return
    _set_setting(ctx.db, "default_min_pct", pct)
    audit(ctx, "default_policy", "settings", "default_min_pct", str(pct))
    messagebox.showinfo("Saved", f"Default min % = {pct}", parent=ctx.parent)


@safe("Status vocabulary")
def feat_16_status_vocabulary(ctx: AdminContext):
    """Manage configurable attendance status codes."""
    win = tk.Toplevel(ctx.parent)
    win.title("Status vocabulary")
    win.geometry("560x420")
    tree = ttk.Treeview(win, columns=("code", "label", "counts_as"), show="headings")
    for c, w in zip(("code", "label", "counts_as"), (120, 200, 140)):
        tree.heading(c, text=c)
        tree.column(c, width=w)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    def refresh():
        for i in tree.get_children():
            tree.delete(i)
        for row in ctx.db.cur.execute(
                "SELECT code, label, counts_as FROM abs_tracker_statuses ORDER BY code"):
            tree.insert("", "end", values=row)

    def add():
        code = simpledialog.askstring("Code", "Status code:", parent=win)
        if not code:
            return
        label = simpledialog.askstring("Label", "Display label:", parent=win) or code
        counts = simpledialog.askstring(
            "Counts as", "Counts as (present/absent/late/excused):",
            parent=win) or "absent"
        ctx.db.cur.execute(
            "INSERT OR REPLACE INTO abs_tracker_statuses (code,label,counts_as) VALUES (?,?,?)",
            (code, label, counts))
        ctx.db.conn.commit()
        audit(ctx, "status_add", "abs_tracker_statuses", code, label)
        refresh()

    tk.Button(win, text="➕ Add", command=add, bg="#16a34a", fg="white",
              relief="flat").pack(pady=6)
    refresh()


@safe("Auto-excuse rules")
def feat_17_auto_excuse_rules(ctx: AdminContext):
    """Auto-excuse dates matching calendar event types."""
    ev_type = simpledialog.askstring(
        "Event type",
        "Academic calendar event_type to auto-excuse (e.g. 'holiday','exam'):",
        parent=ctx.parent)
    if not ev_type:
        return
    ctx.db.cur.execute(
        "INSERT INTO abs_tracker_auto_excuse_rules (event_type) VALUES (?)",
        (ev_type,))
    ctx.db.conn.commit()

    events = ctx.db.cur.execute(
        "SELECT date FROM academic_calendar_events WHERE event_type=?", (ev_type,)).fetchall()
    updated = 0
    for (d,) in events:
        cur = ctx.db.cur.execute(
            "UPDATE attendance SET status='excused', reason='auto: '||? WHERE date=? AND status='absent'",
            (ev_type, d))
        updated += cur.rowcount
    ctx.db.conn.commit()
    audit(ctx, "auto_excuse", "attendance", ev_type, f"updated={updated}")
    messagebox.showinfo("Applied", f"Auto-excused {updated} absence(s) for '{ev_type}'.",
                        parent=ctx.parent)


@safe("Grace period")
def feat_18_grace_period(ctx: AdminContext):
    """Global late→present grace minutes."""
    mins = simpledialog.askinteger(
        "Grace minutes",
        f"Global grace (current {_get_setting(ctx.db,'global_grace','0')}):",
        parent=ctx.parent, minvalue=0, maxvalue=120)
    if mins is None:
        return
    _set_setting(ctx.db, "global_grace", mins)
    audit(ctx, "grace_period", "settings", "global_grace", str(mins))
    messagebox.showinfo("Saved", f"Global grace = {mins} min", parent=ctx.parent)


# ===========================================================================
# 19–26  Reporting
# ===========================================================================

@safe("At-risk students")
def feat_19_at_risk(ctx: AdminContext):
    """List students with attendance below a threshold across a window."""
    threshold = simpledialog.askfloat("Threshold", "Below what % counts as at-risk?",
                                      parent=ctx.parent, minvalue=0, maxvalue=100,
                                      initialvalue=80) or 80
    rows = ctx.db.cur.execute(
        """SELECT a.student_id,
                  COALESCE(s.first_name||' '||s.last_name, a.student_id) AS name,
                  SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) * 100 AS pct,
                  COUNT(*) AS total
           FROM attendance a
           LEFT JOIN students s ON s.student_id = a.student_id
           GROUP BY a.student_id HAVING pct < ?
           ORDER BY pct ASC""", (threshold,)).fetchall()
    audit(ctx, "at_risk_report", "attendance", "", f"threshold={threshold} n={len(rows)}")
    _show_table(ctx.parent, f"At-risk (<{threshold:.0f}%)",
                ("student_id", "name", "pct", "sessions"), rows,
                widths=[110, 260, 90, 90])


@safe("Module health")
def feat_20_module_health(ctx: AdminContext):
    """Average attendance % per module."""
    rows = ctx.db.cur.execute(
        """SELECT a.module_code,
                  COALESCE(m.module_name, a.module_code) AS name,
                  SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) * 100,
                  COUNT(*) AS total
           FROM attendance a LEFT JOIN modules m ON m.module_code = a.module_code
           GROUP BY a.module_code ORDER BY 3 ASC""").fetchall()
    _show_table(ctx.parent, "Module health",
                ("module", "name", "avg %", "rows"), rows,
                widths=[110, 360, 90, 90])


@safe("Cohort compare")
def feat_21_cohort_compare(ctx: AdminContext):
    """Compare attendance by cohort (students.course field)."""
    rows = ctx.db.cur.execute(
        """SELECT COALESCE(s.course,'(none)') AS cohort,
                  COUNT(DISTINCT s.student_id) AS students,
                  SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) * 1.0 /
                    NULLIF(COUNT(a.id),0) * 100 AS avg_pct
           FROM students s LEFT JOIN attendance a ON a.student_id = s.student_id
           GROUP BY cohort ORDER BY 3 DESC""").fetchall()
    _show_table(ctx.parent, "Cohort comparison",
                ("cohort", "students", "avg %"), rows,
                widths=[320, 110, 110])


@safe("Trend chart")
def feat_22_trend_chart(ctx: AdminContext):
    """Rolling 4-week attendance % per module (text-based sparkline)."""
    weeks = ctx.db.cur.execute(
        """SELECT strftime('%Y-%W', date) AS wk,
                  a.module_code,
                  SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) * 1.0 /
                    COUNT(*) * 100
           FROM attendance a GROUP BY wk, a.module_code ORDER BY wk""").fetchall()
    _show_table(ctx.parent, "Weekly % per module",
                ("week", "module", "pct"), weeks, widths=[110, 140, 120])


@safe("Term compare")
def feat_23_term_compare(ctx: AdminContext):
    """Compare attendance across semesters/academic years."""
    rows = ctx.db.cur.execute(
        """SELECT s.name AS semester, s.start_date, s.end_date,
                  SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) * 1.0 /
                    NULLIF(COUNT(a.id),0) * 100 AS pct,
                  COUNT(a.id) AS rows
           FROM semesters s
           LEFT JOIN attendance a ON a.date BETWEEN s.start_date AND s.end_date
           GROUP BY s.id ORDER BY s.start_date""").fetchall()
    _show_table(ctx.parent, "Term-over-term",
                ("semester", "start", "end", "pct", "rows"), rows)


@safe("Schedule report")
def feat_24_schedule_report(ctx: AdminContext):
    """Schedule a recurring attendance report."""
    name = simpledialog.askstring("Name", "Report name:", parent=ctx.parent)
    if not name:
        return
    freq = _combo_dialog(ctx.parent, "Frequency", "Frequency:",
                         ["daily", "weekly", "monthly"]) or "weekly"
    recips = simpledialog.askstring("Recipients",
                                    "Comma-separated emails:", parent=ctx.parent) or ""
    rtype = _combo_dialog(ctx.parent, "Type", "Report type:",
                          ["at_risk", "module_health", "cohort_compare"]) or "at_risk"
    ctx.db.cur.execute(
        """INSERT INTO abs_tracker_scheduled_reports
           (name, frequency, recipients, report_type) VALUES (?,?,?,?)""",
        (name, freq, recips, rtype))
    ctx.db.conn.commit()
    audit(ctx, "schedule_report", "abs_tracker_scheduled_reports", "",
          f"{name} {freq} {rtype}")
    messagebox.showinfo("Scheduled",
                        f"{name} ({freq}) → {recips or '(none)'}", parent=ctx.parent)


@safe("Consecutive absences")
def feat_25_consecutive_absences(ctx: AdminContext):
    """Top-N students with the longest consecutive-absence streak."""
    n = simpledialog.askinteger("Top N", "How many to show?",
                                parent=ctx.parent, minvalue=1, initialvalue=20) or 20
    rows = ctx.db.cur.execute(
        """SELECT student_id, COUNT(*) AS absences
           FROM attendance WHERE status='absent'
           GROUP BY student_id ORDER BY absences DESC LIMIT ?""", (n,)).fetchall()
    _show_table(ctx.parent, f"Top {n} by absence count",
                ("student", "absences"), rows, widths=[180, 120])


@safe("Heatmap")
def feat_26_heatmap(ctx: AdminContext):
    """Absences broken down by day-of-week."""
    rows = ctx.db.cur.execute(
        """SELECT CASE strftime('%w', date)
                    WHEN '0' THEN 'Sun' WHEN '1' THEN 'Mon'
                    WHEN '2' THEN 'Tue' WHEN '3' THEN 'Wed'
                    WHEN '4' THEN 'Thu' WHEN '5' THEN 'Fri'
                    WHEN '6' THEN 'Sat' END AS dow,
                  COUNT(*) AS absences
           FROM attendance WHERE status='absent'
           GROUP BY dow ORDER BY dow""").fetchall()
    _show_table(ctx.parent, "Absences by day-of-week",
                ("day", "absences"), rows, widths=[140, 140])


# ===========================================================================
# 27–30  Notifications
# ===========================================================================

@safe("Threshold alerts")
def feat_27_threshold_alerts(ctx: AdminContext):
    """Create notification rows for students crossing an attendance threshold."""
    threshold = simpledialog.askfloat("Threshold", "Alert below %:",
                                      parent=ctx.parent, initialvalue=75) or 75
    rows = ctx.db.cur.execute(
        """SELECT a.student_id,
                  SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) * 1.0 /
                    COUNT(*) * 100 AS pct
           FROM attendance a GROUP BY a.student_id HAVING pct < ?""",
        (threshold,)).fetchall()
    created = 0
    for sid, pct in rows:
        try:
            ctx.db.cur.execute(
                """INSERT INTO parent_notifications
                   (parent_id, student_id, notification_type, notification_content, created_date, read_status)
                   VALUES ('', ?, 'attendance_alert', ?, ?, 0)""",
                (sid, f"Attendance at {pct:.1f}% (below {threshold:.0f}%)",
                 datetime.now().isoformat(timespec="seconds")))
            created += 1
        except Exception:
            logger.exception("parent notif for %s failed", sid)
    ctx.db.conn.commit()
    audit(ctx, "threshold_alerts", "parent_notifications", "",
          f"threshold={threshold} created={created}")
    messagebox.showinfo("Alerts", f"Created {created} alert(s).", parent=ctx.parent)


@safe("Parent notifications")
def feat_28_parent_notifications(ctx: AdminContext):
    """Notify parents of a student's recent absences via parent_notifications."""
    sid = _pick_student(ctx, "Notify parents of which student?")
    if not sid:
        return
    parents = ctx.db.cur.execute(
        "SELECT parent_id FROM parent_student_links WHERE student_id=?",
        (sid,)).fetchall()
    if not parents:
        messagebox.showinfo("No parents",
                            "No parents linked to this student.", parent=ctx.parent)
        return
    recent = ctx.db.cur.execute(
        "SELECT date, status FROM attendance WHERE student_id=? ORDER BY date DESC LIMIT 10",
        (sid,)).fetchall()
    content = f"Recent attendance: " + "; ".join(f"{d}={s}" for d, s in recent)
    for (pid,) in parents:
        ctx.db.cur.execute(
            """INSERT INTO parent_notifications
               (parent_id, student_id, notification_type, notification_content, created_date, read_status)
               VALUES (?, ?, 'attendance_update', ?, ?, 0)""",
            (str(pid), sid, content, datetime.now().isoformat(timespec="seconds")))
    ctx.db.conn.commit()
    audit(ctx, "parent_notify", "parent_notifications", sid, f"parents={len(parents)}")
    messagebox.showinfo("Sent", f"Notified {len(parents)} parent(s).", parent=ctx.parent)


@safe("Bulk announcement")
def feat_29_bulk_announcement(ctx: AdminContext):
    """Create parent_notifications for every student on a module's roster."""
    mc = _pick_module(ctx, "Announce to which module?")
    if not mc:
        return
    msg = simpledialog.askstring("Message", "Announcement text:", parent=ctx.parent)
    if not msg:
        return
    roster = ctx.db.get_course_students(mc)
    for sid, *_ in roster:
        ctx.db.cur.execute(
            """INSERT INTO parent_notifications
               (parent_id, student_id, notification_type, notification_content, created_date, read_status)
               VALUES ('', ?, 'announcement', ?, ?, 0)""",
            (sid, msg, datetime.now().isoformat(timespec="seconds")))
    ctx.db.conn.commit()
    audit(ctx, "bulk_announcement", "parent_notifications", mc,
          f"n={len(roster)} msg={msg[:80]}")
    messagebox.showinfo("Sent", f"Announcement to {len(roster)} student(s).",
                        parent=ctx.parent)


@safe("SMS fallback")
def feat_30_sms_fallback(ctx: AdminContext):
    """Queue SMS messages for parents of at-risk students (via sms_messages)."""
    threshold = simpledialog.askfloat("Threshold", "Below %:",
                                      parent=ctx.parent, initialvalue=70) or 70
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS sms_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, recipient TEXT, body TEXT,
        queued_at TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'queued')""")
    rows = ctx.db.cur.execute(
        """SELECT a.student_id,
                  SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) * 1.0 /
                    COUNT(*) * 100 AS pct
           FROM attendance a GROUP BY a.student_id HAVING pct < ?""",
        (threshold,)).fetchall()
    queued = 0
    for sid, pct in rows:
        ctx.db.cur.execute(
            "INSERT INTO sms_messages (recipient, body) VALUES (?,?)",
            (sid, f"ALERT: attendance {pct:.1f}% below {threshold:.0f}%"))
        queued += 1
    ctx.db.conn.commit()
    audit(ctx, "sms_queue", "sms_messages", "", f"n={queued}")
    messagebox.showinfo("Queued", f"{queued} SMS message(s) queued.", parent=ctx.parent)


# ===========================================================================
# 31–37  Integrations
# ===========================================================================

@safe("Calendar link")
def feat_31_calendar_link(ctx: AdminContext):
    """Show academic_calendar_events in the next N days."""
    n = simpledialog.askinteger("Window", "Look ahead how many days?",
                                parent=ctx.parent, initialvalue=30) or 30
    today = date.today().isoformat()
    end = (date.today() + timedelta(days=n)).isoformat()
    rows = ctx.db.cur.execute(
        """SELECT date, name, event_type FROM academic_calendar_events
           WHERE date BETWEEN ? AND ? ORDER BY date""", (today, end)).fetchall()
    _show_table(ctx.parent, f"Calendar ({today} → {end})",
                ("date", "name", "type"), rows, widths=[120, 480, 140])


@safe("Pre-generate sessions")
def feat_32_schedule_sessions(ctx: AdminContext):
    """Preview class sessions from module_schedule for a given module."""
    mc = _pick_module(ctx, "Sessions for which module?")
    if not mc:
        return
    rows = ctx.db.cur.execute(
        """SELECT day_of_week, start_time, end_time, room_id, instructor_id, semester, year, status
           FROM module_schedule WHERE module_code=? ORDER BY day_of_week, start_time""",
        (mc,)).fetchall()
    _show_table(ctx.parent, f"Scheduled sessions for {mc}",
                ("day", "start", "end", "room", "instructor", "sem", "yr", "status"),
                rows)


@safe("Risk feed")
def feat_33_risk_feed(ctx: AdminContext):
    """Feed current attendance into student_risk_assessment."""
    rows = ctx.db.cur.execute(
        """SELECT student_id,
                  SUM(CASE WHEN status='present' THEN 1 ELSE 0 END) * 1.0 /
                    COUNT(*) * 100 AS pct, COUNT(*)
           FROM attendance GROUP BY student_id""").fetchall()
    created = 0
    today = date.today().isoformat()
    for sid, pct, _tot in rows:
        pct = pct or 0
        level = "low" if pct >= 85 else "medium" if pct >= 70 else "high"
        score = round(100 - pct, 2)
        ctx.db.cur.execute(
            """INSERT INTO student_risk_assessment
               (student_id, risk_score, risk_level, assessment_date, prediction_model, confidence)
               VALUES (?,?,?,?,?,?)""",
            (sid, score, level, today, "attendance_basic", 0.9))
        created += 1
    ctx.db.conn.commit()
    audit(ctx, "risk_feed", "student_risk_assessment", "", f"rows={created}")
    messagebox.showinfo("Done", f"Wrote {created} risk rows.", parent=ctx.parent)


@safe("Grade link")
def feat_34_grade_link(ctx: AdminContext):
    """Flag students whose attendance may trigger a grade penalty."""
    threshold = simpledialog.askfloat("Threshold", "Penalty below %:",
                                      parent=ctx.parent, initialvalue=50) or 50
    rows = ctx.db.cur.execute(
        """SELECT a.student_id, a.module_code,
                  SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)*1.0/COUNT(*)*100
           FROM attendance a GROUP BY a.student_id, a.module_code
           HAVING 3 < ?""", (threshold,)).fetchall()
    _show_table(ctx.parent, f"Attendance penalty candidates (<{threshold:.0f}%)",
                ("student", "module", "pct"), rows)
    audit(ctx, "grade_link", "attendance", "", f"threshold={threshold} n={len(rows)}")


@safe("Wellbeing link")
def feat_35_wellbeing_link(ctx: AdminContext):
    """Cross-reference absences with wellbeing check-ins."""
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS mental_health_checkins
        (id INTEGER PRIMARY KEY, student_id TEXT, mood INTEGER, checkin_date TEXT)""")
    rows = ctx.db.cur.execute(
        """SELECT a.student_id,
                  SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END) AS abs_cnt,
                  (SELECT AVG(mood) FROM mental_health_checkins mc
                   WHERE mc.student_id=a.student_id) AS avg_mood
           FROM attendance a GROUP BY a.student_id
           ORDER BY abs_cnt DESC LIMIT 50""").fetchall()
    _show_table(ctx.parent, "Absences vs mood",
                ("student", "absences", "avg_mood"), rows)


@safe("Disciplinary action")
def feat_36_disciplinary_action(ctx: AdminContext):
    """Create a disciplinary_actions row for repeat offenders."""
    sid = _pick_student(ctx, "Disciplinary action for?")
    if not sid:
        return
    reason = simpledialog.askstring("Reason", "Reason:", parent=ctx.parent) or \
             "Repeated unjustified absences"
    ctx.db.cur.execute(
        """INSERT INTO disciplinary_actions
           (record_id, action_type, action_level, effective_date, duration_days,
            imposed_by, reason, created_at)
           VALUES (0, 'warning', 'written', ?, 0, ?, ?, ?)""",
        (date.today().isoformat(), ctx.user.get("username"), reason,
         datetime.now().isoformat(timespec="seconds")))
    ctx.db.conn.commit()
    audit(ctx, "disciplinary", "disciplinary_actions", sid, reason)
    messagebox.showinfo("Recorded", f"Disciplinary action logged for {sid}.",
                        parent=ctx.parent)


@safe("Finance link")
def feat_37_finance_link(ctx: AdminContext):
    """Cross-reference scholarship students whose attendance is below threshold."""
    threshold = simpledialog.askfloat("Threshold", "Below %:",
                                      parent=ctx.parent, initialvalue=80) or 80
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS student_scholarships
        (id INTEGER PRIMARY KEY, student_id TEXT, scholarship_id INTEGER, status TEXT)""")
    rows = ctx.db.cur.execute(
        """SELECT ss.student_id,
                  SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)*1.0/NULLIF(COUNT(a.id),0)*100
           FROM student_scholarships ss
           LEFT JOIN attendance a ON a.student_id = ss.student_id
           GROUP BY ss.student_id HAVING 2 < ?""", (threshold,)).fetchall()
    _show_table(ctx.parent, "Scholarship attendance check",
                ("student", "pct"), rows)


# ===========================================================================
# 38–41  Bulk operations
# ===========================================================================

@safe("Bulk present")
def feat_38_bulk_mark_present(ctx: AdminContext):
    """Mark every student in a module present on a date."""
    mc = _pick_module(ctx, "Module:")
    if not mc:
        return
    d = simpledialog.askstring("Date", "Date (YYYY-MM-DD):",
                               parent=ctx.parent,
                               initialvalue=date.today().isoformat())
    if not d:
        return
    roster = ctx.db.get_course_students(mc)
    for sid, *_ in roster:
        ctx.db.record_absence(sid, mc, d, "present", "bulk-present")
    audit(ctx, "bulk_present", "attendance", mc, f"date={d} n={len(roster)}")
    messagebox.showinfo("Saved", f"Marked {len(roster)} present on {d}.",
                        parent=ctx.parent)


@safe("Copy previous day")
def feat_39_copy_previous_day(ctx: AdminContext):
    """Copy the most recent attendance roll for a module to today."""
    mc = _pick_module(ctx, "Module:")
    if not mc:
        return
    d = simpledialog.askstring("Copy to date",
                               "Target date (YYYY-MM-DD):",
                               parent=ctx.parent,
                               initialvalue=date.today().isoformat())
    if not d:
        return
    last = ctx.db.cur.execute(
        "SELECT MAX(date) FROM attendance WHERE module_code=? AND date<?",
        (mc, d)).fetchone()[0]
    if not last:
        messagebox.showinfo("Nothing to copy", "No prior attendance rows.",
                            parent=ctx.parent)
        return
    rows = ctx.db.cur.execute(
        "SELECT student_id, status, reason FROM attendance WHERE module_code=? AND date=?",
        (mc, last)).fetchall()
    for sid, status, reason in rows:
        ctx.db.record_absence(sid, mc, d, status, reason or "")
    audit(ctx, "copy_prev_day", "attendance", mc, f"from={last} to={d} n={len(rows)}")
    messagebox.showinfo("Copied", f"Copied {len(rows)} row(s) {last} → {d}.",
                        parent=ctx.parent)


@safe("Recurring absence")
def feat_40_recurring_absence(ctx: AdminContext):
    """Mark a student absent on the same day-of-week for N weeks."""
    sid = _pick_student(ctx, "Student:")
    if not sid:
        return
    mc = _pick_module(ctx, "Module:")
    if not mc:
        return
    start = simpledialog.askstring("First date", "First date (YYYY-MM-DD):",
                                   parent=ctx.parent,
                                   initialvalue=date.today().isoformat())
    weeks = simpledialog.askinteger("Weeks", "How many weeks?",
                                    parent=ctx.parent, minvalue=1, maxvalue=52)
    status = _combo_dialog(ctx.parent, "Status", "Status:",
                           ["absent", "excused", "late", "present"]) or "absent"
    if not (start and weeks):
        return
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    for w in range(weeks):
        d = (d0 + timedelta(days=7 * w)).isoformat()
        ctx.db.record_absence(sid, mc, d, status, "recurring")
    audit(ctx, "recurring_absence", "attendance", sid,
          f"{mc} {start} x{weeks} {status}")
    messagebox.showinfo("Saved", f"Created {weeks} rows for {sid}.",
                        parent=ctx.parent)


@safe("Reassign records")
def feat_41_reassign_records(ctx: AdminContext):
    """Re-key attendance rows when a student transfers modules."""
    sid = _pick_student(ctx, "Student:")
    src = _pick_module(ctx, "Source module:")
    dst = _pick_module(ctx, "Destination module:")
    if not (sid and src and dst):
        return
    cur = ctx.db.cur.execute(
        "UPDATE attendance SET module_code=? WHERE student_id=? AND module_code=?",
        (dst, sid, src))
    ctx.db.conn.commit()
    audit(ctx, "reassign", "attendance", sid, f"{src}→{dst} n={cur.rowcount}")
    messagebox.showinfo("Reassigned",
                        f"Moved {cur.rowcount} row(s) {src} → {dst}.",
                        parent=ctx.parent)


# ===========================================================================
# 42–46  Access, security & audit
# ===========================================================================

@safe("Permission matrix")
def feat_42_permission_matrix(ctx: AdminContext):
    """Show which staff user can approve requests for which modules."""
    rows = ctx.db.cur.execute(
        """SELECT u.username, u.role, im.module_code
           FROM users u LEFT JOIN instructor_modules im ON im.instructor_id = u.id
           WHERE u.role IN ('admin','staff','instructor')
           ORDER BY u.username""").fetchall()
    _show_table(ctx.parent, "Permission matrix",
                ("user", "role", "module"), rows)


@safe("Full audit trail")
def feat_43_full_audit_trail(ctx: AdminContext):
    """Display full admin audit trail with filter."""
    user = simpledialog.askstring("Filter",
                                  "Filter by username (blank = all):",
                                  parent=ctx.parent) or ""
    q = "SELECT ts, username, action, target, target_id, details FROM abs_tracker_audit"
    p = []
    if user:
        q += " WHERE username LIKE ?"
        p.append(f"%{user}%")
    q += " ORDER BY ts DESC LIMIT 1000"
    rows = ctx.db.cur.execute(q, p).fetchall()
    _show_table(ctx.parent, "Full audit trail",
                ("ts", "user", "action", "target", "id", "details"), rows,
                widths=[150, 120, 140, 100, 100, 350])


@safe("Impersonate")
def feat_44_impersonate(ctx: AdminContext):
    """Open a read-only view as another user would see it."""
    username = simpledialog.askstring("Impersonate", "Username to view as:",
                                      parent=ctx.parent)
    if not username:
        return
    other = ctx.db.lookup_user_by_username(username)
    if not other:
        messagebox.showerror("Not found", f"No user '{username}'", parent=ctx.parent)
        return
    # Import the sibling module lazily to avoid a cycle
    from education_system.university_system.modules.domain.academics.attendance \
        import absence_tracker as at
    new_root = tk.Toplevel(ctx.parent)
    at.launch_dashboard(new_root, ctx.db, other)
    audit(ctx, "impersonate", "users", other["id"], username)


@safe("Retention purge")
def feat_45_retention_purge(ctx: AdminContext):
    """Delete attendance rows older than N years per retention policy."""
    years = simpledialog.askinteger("Retention",
                                    "Purge attendance older than (years)?",
                                    parent=ctx.parent, minvalue=1, maxvalue=30)
    if not years:
        return
    cutoff = (date.today() - timedelta(days=365 * years)).isoformat()
    cur = ctx.db.cur.execute("DELETE FROM attendance WHERE date < ?", (cutoff,))
    removed = cur.rowcount
    ctx.db.cur.execute(
        "INSERT INTO abs_tracker_retention (policy, years, applied_at) VALUES (?,?,?)",
        (f"attendance<{cutoff}", years, datetime.now().isoformat(timespec="seconds")))
    ctx.db.conn.commit()
    audit(ctx, "retention_purge", "attendance", "", f"years={years} removed={removed}")
    messagebox.showinfo("Purged", f"Removed {removed} row(s) before {cutoff}.",
                        parent=ctx.parent)


@safe("GDPR export")
def feat_46_gdpr_export(ctx: AdminContext):
    """Export every absence record for a single student (GDPR subject access)."""
    sid = _pick_student(ctx, "Export data for which student?")
    if not sid:
        return
    att = ctx.db.cur.execute(
        "SELECT * FROM attendance WHERE student_id=?", (sid,)).fetchall()
    req = ctx.db.cur.execute(
        "SELECT * FROM absence_requests WHERE student_id=?", (sid,)).fetchall()
    path = filedialog.asksaveasfilename(
        parent=ctx.parent, defaultextension=".json",
        initialfile=f"gdpr_{sid}.json")
    if not path:
        return
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"student_id": sid,
                   "attendance": [list(r) for r in att],
                   "absence_requests": [list(r) for r in req]}, fh, indent=2)
    audit(ctx, "gdpr_export", "students", sid, path)
    messagebox.showinfo("Exported", f"Data written:\n{path}", parent=ctx.parent)


# ===========================================================================
# 47–50  Data quality & diagnostics
# ===========================================================================

@safe("Orphan rows")
def feat_47_orphan_rows(ctx: AdminContext):
    """Find attendance rows whose student_id or module_code no longer exists."""
    rows = ctx.db.cur.execute(
        """SELECT a.id, a.student_id, a.module_code, a.date,
                  CASE WHEN s.student_id IS NULL THEN 'missing student' ELSE '' END,
                  CASE WHEN m.module_code IS NULL THEN 'missing module' ELSE '' END
           FROM attendance a
           LEFT JOIN students s ON s.student_id = a.student_id
           LEFT JOIN modules m  ON m.module_code = a.module_code
           WHERE s.student_id IS NULL OR m.module_code IS NULL
           ORDER BY a.date DESC""").fetchall()
    _show_table(ctx.parent, f"Orphan rows ({len(rows)})",
                ("id", "student_id", "module_code", "date", "student?", "module?"), rows)
    audit(ctx, "orphan_scan", "attendance", "", f"n={len(rows)}")


@safe("Missing sessions")
def feat_48_missing_sessions(ctx: AdminContext):
    """Scheduled sessions that have no attendance rows recorded."""
    rows = ctx.db.cur.execute(
        """SELECT ms.module_code, ms.day_of_week, ms.start_time, ms.semester
           FROM module_schedule ms
           LEFT JOIN attendance a ON a.module_code = ms.module_code
           WHERE a.id IS NULL
           ORDER BY ms.module_code""").fetchall()
    _show_table(ctx.parent, f"Modules with scheduled sessions but no attendance ({len(rows)})",
                ("module", "day", "start", "semester"), rows)


@safe("Enrollment mismatch")
def feat_49_enrollment_mismatch(ctx: AdminContext):
    """Attendance rows for students not enrolled in that module."""
    rows = ctx.db.cur.execute(
        """SELECT a.id, a.student_id, a.module_code, a.date
           FROM attendance a
           LEFT JOIN student_modules sm
             ON sm.student_id = a.student_id AND sm.module_code = a.module_code
           WHERE sm.id IS NULL
           ORDER BY a.date DESC""").fetchall()
    _show_table(ctx.parent, f"Enrollment mismatches ({len(rows)})",
                ("id", "student", "module", "date"), rows)
    audit(ctx, "enrollment_mismatch", "attendance", "", f"n={len(rows)}")


@safe("DB health")
def feat_50_db_health(ctx: AdminContext):
    """Database health panel — row counts, integrity check, WAL mode."""
    stats = []
    for t in ("attendance", "absence_requests", "students", "modules",
              "student_modules", "instructor_modules", "users",
              "abs_tracker_audit", "abs_tracker_trash"):
        try:
            n = ctx.db.cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            stats.append((t, n, "ok"))
        except Exception as e:
            stats.append((t, "?", str(e)))
    integrity = ctx.db.cur.execute("PRAGMA integrity_check").fetchone()[0]
    journal = ctx.db.cur.execute("PRAGMA journal_mode").fetchone()[0]
    page_size = ctx.db.cur.execute("PRAGMA page_size").fetchone()[0]
    page_count = ctx.db.cur.execute("PRAGMA page_count").fetchone()[0]
    size_mb = (page_size * page_count) / 1_048_576

    stats.append(("integrity_check", integrity, ""))
    stats.append(("journal_mode", journal, ""))
    stats.append(("size_mb", f"{size_mb:.2f}", ""))
    stats.append(("db_path", ctx.db.path, ""))

    _show_table(ctx.parent, "Database health",
                ("metric", "value", "note"), stats, widths=[220, 500, 200])
    audit(ctx, "db_health", "db", "", f"size_mb={size_mb:.2f}")


# ---------------------------------------------------------------------------
# Registry: ordered list of (number, category, label, callable)
# ---------------------------------------------------------------------------
FEATURES: list[tuple[int, str, str, Callable]] = [
    # Attendance data management
    (1,  "Data",          "Bulk import CSV",                feat_01_bulk_import),
    (2,  "Data",          "Bulk export CSV",                feat_02_bulk_export),
    (3,  "Data",          "Edit record in place",           feat_03_edit_record),
    (4,  "Data",          "Undo delete (24h trash)",        feat_04_undo_delete),
    (5,  "Data",          "Merge duplicate rows",           feat_05_merge_duplicates),
    (6,  "Data",          "Correction audit log",           feat_06_correction_audit),
    (7,  "Data",          "Lock past dates",                feat_07_lock_past_dates),
    # Requests
    (8,  "Requests",      "Bulk approve / reject",          feat_08_bulk_approve_reject),
    (9,  "Requests",      "Attach document to request",     feat_09_request_attachment),
    (10, "Requests",      "Auto-expire old pending",        feat_10_expire_pending),
    (11, "Requests",      "Delegate approval",              feat_11_delegate_approval),
    (12, "Requests",      "Comment thread on request",      feat_12_request_comment_thread),
    (13, "Requests",      "Manage request templates",       feat_13_request_templates),
    # Policies
    (14, "Policies",      "Per-module policy",              feat_14_module_policy),
    (15, "Policies",      "Default university policy",      feat_15_default_policy),
    (16, "Policies",      "Status vocabulary",              feat_16_status_vocabulary),
    (17, "Policies",      "Auto-excuse rules",              feat_17_auto_excuse_rules),
    (18, "Policies",      "Global grace period",            feat_18_grace_period),
    # Reporting
    (19, "Reports",       "At-risk students",               feat_19_at_risk),
    (20, "Reports",       "Module health",                  feat_20_module_health),
    (21, "Reports",       "Cohort comparison",              feat_21_cohort_compare),
    (22, "Reports",       "Weekly trend",                   feat_22_trend_chart),
    (23, "Reports",       "Term-over-term",                 feat_23_term_compare),
    (24, "Reports",       "Schedule recurring report",      feat_24_schedule_report),
    (25, "Reports",       "Top consecutive absences",       feat_25_consecutive_absences),
    (26, "Reports",       "Day-of-week heatmap",            feat_26_heatmap),
    # Notifications
    (27, "Notifications", "Threshold alerts",               feat_27_threshold_alerts),
    (28, "Notifications", "Parent notifications",           feat_28_parent_notifications),
    (29, "Notifications", "Bulk announcement",              feat_29_bulk_announcement),
    (30, "Notifications", "SMS fallback queue",             feat_30_sms_fallback),
    # Integrations
    (31, "Integrations",  "Calendar events link",           feat_31_calendar_link),
    (32, "Integrations",  "Module schedule sessions",       feat_32_schedule_sessions),
    (33, "Integrations",  "Feed student risk model",        feat_33_risk_feed),
    (34, "Integrations",  "Grade penalty candidates",       feat_34_grade_link),
    (35, "Integrations",  "Wellbeing cross-reference",      feat_35_wellbeing_link),
    (36, "Integrations",  "Raise disciplinary action",      feat_36_disciplinary_action),
    (37, "Integrations",  "Scholarship attendance check",   feat_37_finance_link),
    # Bulk
    (38, "Bulk",          "Mark whole class present",       feat_38_bulk_mark_present),
    (39, "Bulk",          "Copy previous day",              feat_39_copy_previous_day),
    (40, "Bulk",          "Recurring absence",              feat_40_recurring_absence),
    (41, "Bulk",          "Reassign records on transfer",   feat_41_reassign_records),
    # Security
    (42, "Security",      "Permission matrix",              feat_42_permission_matrix),
    (43, "Security",      "Full audit trail",               feat_43_full_audit_trail),
    (44, "Security",      "Impersonate (read-only)",        feat_44_impersonate),
    (45, "Security",      "Retention purge",                feat_45_retention_purge),
    (46, "Security",      "GDPR subject export",            feat_46_gdpr_export),
    # Diagnostics
    (47, "Diagnostics",   "Orphan attendance rows",         feat_47_orphan_rows),
    (48, "Diagnostics",   "Missing sessions",               feat_48_missing_sessions),
    (49, "Diagnostics",   "Enrollment mismatch",            feat_49_enrollment_mismatch),
    (50, "Diagnostics",   "Database health",                feat_50_db_health),
]


# ---------------------------------------------------------------------------
# Soft-delete override so Undo (feature 4) works
# ---------------------------------------------------------------------------
def install_soft_delete(db) -> None:
    """Wrap Database.delete_absence so deletions land in the 24h trash."""
    if getattr(db, "_soft_delete_installed", False):
        return
    original = db.delete_absence

    def soft_delete(absence_id: int) -> None:
        try:
            row = db.cur.execute(
                "SELECT id, student_id, module_code, date, status, reason FROM attendance WHERE id=?",
                (absence_id,)).fetchone()
            if row:
                payload = json.dumps({
                    "id": row[0], "student_id": row[1], "module_code": row[2],
                    "date": row[3], "status": row[4], "reason": row[5],
                })
                db.cur.execute(
                    """INSERT INTO abs_tracker_trash
                       (deleted_by, original_table, original_id, payload)
                       VALUES (?, 'attendance', ?, ?)""",
                    ("admin", row[0], payload))
        except Exception:
            logger.exception("soft-delete snapshot failed id=%s", absence_id)
        original(absence_id)

    db.delete_absence = soft_delete
    db._soft_delete_installed = True


def build_admin_tab(notebook: ttk.Notebook, ctx: AdminContext) -> None:
    """Render all 50 features into a dedicated Admin Tools tab."""
    ensure_support_tables(ctx.db)
    install_soft_delete(ctx.db)

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

    # Group by category
    by_cat: dict[str, list[tuple[int, str, Callable]]] = {}
    for n, cat, label, fn in FEATURES:
        by_cat.setdefault(cat, []).append((n, label, fn))

    for cat, items in by_cat.items():
        box = tk.LabelFrame(inner, text=cat, padx=10, pady=8,
                            font=("Arial", 11, "bold"), bg="#f0f4f8",
                            fg="#1e3a5f")
        box.pack(fill="x", padx=12, pady=8)
        cols = 3
        for i, (num, label, fn) in enumerate(items):
            btn = tk.Button(
                box, text=f"{num:02d}. {label}",
                command=functools.partial(fn, ctx),
                bg="#2563eb", fg="white", activebackground="#1d4ed8",
                relief="flat", cursor="hand2",
                width=32, anchor="w", padx=8, pady=6,
            )
            btn.grid(row=i // cols, column=i % cols, padx=4, pady=3, sticky="w")

    logger.info("admin tools tab built (%d features)", len(FEATURES))
