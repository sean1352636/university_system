"""CSV export, admin email delivery, and rich report-window helpers."""
from __future__ import annotations

import csv
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import Iterable, Optional

from .context import logger


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
        from education_system.systems.university.infrastructure.email import (
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
